import os
import re
import time
import random
import threading
import mysql.connector
from mysql.connector import errorcode
from flask import Flask, jsonify, render_template, request

# ==========================================
# SYSTEM CONFIGURATION
# ==========================================
COM_PORT = "COM7"
BAUD_RATE = 9600

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = ""
DB_NAME = "robosense_db"

# Set to True if you want to generate high-fidelity simulated values inside MySQL 
# in case real physical hardware is not connected. Set to False for real production.
SIMULATE_DATA = False



# ==========================================
# FLASK & STATE INITIALIZATION
# ==========================================
app = Flask(__name__, template_folder="templates")
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.after_request
def add_header(response):
    """Disable caching for all responses to ensure real-time UI changes render instantly."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Global tracking variables
system_status = {
    "connection": "DISCONNECTED",  # CONNECTED or SIMULATED or DISCONNECTED
    "com_port": COM_PORT,
    "last_reading": None,
    "uptime_start": time.time(),
    "total_readings_logged": 0
}

# Thread lock for thread-safe database operations and state updates
db_lock = threading.Lock()

# Try to import serial (pyserial). If not installed, we'll log and use simulated.
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ==========================================
# DATABASE BOOTSTRAPPING
# ==========================================
def get_db_connection(include_db=True):
    """Establishes and returns a connection to MySQL."""
    try:
        if include_db:
            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME
            )
        else:
            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS
            )
    except mysql.connector.Error as err:
        print(f"[MySQL Connection Error] {err}")
        return None

def bootstrap_database():
    """Bootstraps the MySQL server: creates the database and the sensor_readings table."""
    conn = get_db_connection(include_db=False)
    if not conn:
        print("[DB Bootstrap] Could not connect to MySQL server. Ensure XAMPP MySQL is active. Booting in memory-simulation mode.")
        return False

    cursor = conn.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        print(f"[DB Bootstrap] Database '{DB_NAME}' checked/created successfully.")
    except mysql.connector.Error as err:
        print(f"[DB Bootstrap] Failed to create database: {err}")
        cursor.close()
        conn.close()
        return False
    finally:
        cursor.close()
        conn.close()

    # Create the table
    conn = get_db_connection(include_db=True)
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        table_query = """
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temp_c FLOAT,
            humidity_pct FLOAT,
            soil_pct FLOAT,
            status VARCHAR(20),
            flag VARCHAR(10)
        );
        """
        cursor.execute(table_query)
        conn.commit()
        print("[DB Bootstrap] Table 'sensor_readings' verified/created successfully.")
        
        # Count initial rows
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        system_status["total_readings_logged"] = cursor.fetchone()[0]
        return True
    except mysql.connector.Error as err:
        print(f"[DB Bootstrap] Failed to create table: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

# ==========================================
# DATA INGESTION & PARSING
# ==========================================
def log_reading_to_db(temp, hum, soil, status, flag):
    """Inserts a sensor reading row into MySQL with thread-safety."""
    global system_status
    with db_lock:
        conn = get_db_connection()
        if not conn:
            print("[Database Log Fail] Database not reachable. Skipping write.")
            return False
        
        cursor = conn.cursor()
        try:
            query = """
            INSERT INTO sensor_readings (temp_c, humidity_pct, soil_pct, status, flag)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (temp, hum, soil, status, flag))
            conn.commit()
            
            system_status["total_readings_logged"] += 1
            system_status["last_reading"] = {
                "temp_c": temp,
                "humidity_pct": hum,
                "soil_pct": soil,
                "status": status,
                "flag": flag,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            return True
        except mysql.connector.Error as err:
            print(f"[Database Insert Error] {err}")
            return False
        finally:
            cursor.close()
            conn.close()

def calculate_status_and_flag(temp, hum, soil):
    """Calculates system status and alert flags based on business logic rules."""
    # Soil moisture below 20% is CRITICAL DRY
    if soil < 20.0:
        return "CRITICAL", "DRY"
    # Temperature above 30C is WARNING TEMP
    elif temp > 30.0:
        return "WARN", "TEMP"
    # Otherwise optimal
    else:
        return "OPTIMAL", "OK"

def parse_arduino_line(line):
    """
    Parses strings in the format: TEMP=27.4;HUM=68;SOIL=75
    Returns (temp, humidity, soil) if valid, or None.
    """
    try:
        # Match using regex for clean parsing
        temp_match = re.search(r'TEMP=([0-9.]+)', line)
        hum_match = re.search(r'HUM=([0-9.]+)', line)
        soil_match = re.search(r'SOIL=([0-9.]+)', line)

        if temp_match and hum_match and soil_match:
            temp = float(temp_match.group(1))
            hum = float(hum_match.group(1))
            soil = float(soil_match.group(1))
            return temp, hum, soil
    except Exception as e:
        print(f"[Parser Error] Failed to parse line '{line}': {e}")
    return None

# ==========================================
# BACKGROUND DATA INGESTION WORKER
# ==========================================
def serial_reader_thread():
    """Background thread that reads serial data from COM port or runs high-fidelity simulator."""
    global system_status
    
    print("[Serial Thread] Background serial processor started.")
    ser = None
    
    # Try connecting to physical serial device if available
    if SERIAL_AVAILABLE:
        try:
            print(f"[Serial Thread] Attempting connection to HC-05 on {COM_PORT} ({BAUD_RATE} Baud)...")
            ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=2)
            system_status["connection"] = "CONNECTED"
            print(f"[Serial Thread] Connected to real hardware on {COM_PORT} successfully!")
        except Exception as ex:
            print(f"[Serial Thread] Connection failed on {COM_PORT}: {ex}")
            ser = None
            
    if not ser:
        if SIMULATE_DATA:
            system_status["connection"] = "SIMULATED"
            print("[Serial Thread] Running in high-fidelity SIMULATED mode. Generating realistic sensor values.")
        else:
            system_status["connection"] = "DISCONNECTED"
            print("[Serial Thread] Running in passive/empty mode. Waiting for hardware COM port connection...")

    # Variables for state drift in simulator mode to make data look highly authentic
    sim_temp = 25.5
    sim_hum = 60.0
    sim_soil = 45.0
    
    # Simple drift states to occasionally trigger warnings/critical alert
    drift_cycle = 0
    cycle_timer = 0

    while True:
        try:
            if system_status["connection"] == "CONNECTED" and ser:
                # Read from physical COM port
                if ser.in_waiting > 0:
                    raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if raw_line:
                        print(f"[Hardware Serial IN] {raw_line}")
                        parsed = parse_arduino_line(raw_line)
                        if parsed:
                            temp, hum, soil = parsed
                            status, flag = calculate_status_and_flag(temp, hum, soil)
                            log_reading_to_db(temp, hum, soil, status, flag)
                time.sleep(0.1)
                
            elif system_status["connection"] == "SIMULATED" and SIMULATE_DATA:
                # ==========================================
                # DYNAMIC HIGH-FIDELITY SIMULATOR
                # ==========================================
                cycle_timer += 1
                
                # Every 25 cycles (50s), switch drift state to show all dashboard conditions
                if cycle_timer >= 25:
                    drift_cycle = (drift_cycle + 1) % 3
                    cycle_timer = 0
                    print(f"[Simulator] Cycle shift! Moving to simulation phase: {drift_cycle}")
                
                # Apply drifts based on cycle phase
                if drift_cycle == 0:
                    # Normal drift: values hover around optimal
                    sim_temp += random.uniform(-0.3, 0.3)
                    sim_temp = max(24.0, min(29.0, sim_temp)) # Keep below 30
                    sim_hum += random.uniform(-0.5, 0.5)
                    sim_hum = max(50.0, min(75.0, sim_hum))
                    sim_soil += random.uniform(-1.0, 1.0)
                    sim_soil = max(35.0, min(75.0, sim_soil)) # Keep above 20
                elif drift_cycle == 1:
                    # Heatwave phase: temperature rises above 30C (WARNING TEMP)
                    sim_temp += random.uniform(0.1, 0.5)
                    sim_temp = min(33.5, sim_temp)
                    sim_hum += random.uniform(-0.6, 0.2)
                    sim_hum = max(40.0, sim_hum)
                    sim_soil += random.uniform(-0.8, 0.2)
                    sim_soil = max(25.0, sim_soil)
                elif drift_cycle == 2:
                    # Drought phase: soil moisture drops below 20% (CRITICAL DRY)
                    sim_temp += random.uniform(-0.4, 0.2)
                    sim_temp = max(23.0, sim_temp)
                    sim_hum += random.uniform(-0.8, 0.4)
                    sim_hum = max(35.0, sim_hum)
                    sim_soil -= random.uniform(0.5, 2.5) # Fast drop
                    sim_soil = max(8.0, sim_soil) # Cap at dry level
                    
                # Format exactly as Arduino Serial string for terminal feedback
                sim_line = f"TEMP={sim_temp:.1f};HUM={sim_hum:.0f};SOIL={sim_soil:.0f}"
                print(f"[Simulated Serial Output] {sim_line}")
                
                # Parse and log just like real serial
                parsed = parse_arduino_line(sim_line)
                if parsed:
                    temp, hum, soil = parsed
                    status, flag = calculate_status_and_flag(temp, hum, soil)
                    log_reading_to_db(temp, hum, soil, status, flag)
                
                time.sleep(2.0)
                
            else:
                # Passive disconnected / empty mode: Try to open the COM Port periodically
                if SERIAL_AVAILABLE:
                    try:
                        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=2)
                        system_status["connection"] = "CONNECTED"
                        print(f"[Serial Thread] Hardware port {COM_PORT} opened. Transitioned to CONNECTED!")
                    except Exception:
                        system_status["connection"] = "DISCONNECTED"
                else:
                    system_status["connection"] = "DISCONNECTED"
                time.sleep(5.0)
                
        except Exception as e:
            print(f"[Serial Thread Main Loop Exception] {e}")
            if ser:
                try:
                    ser.close()
                except:
                    pass
            ser = None
            
            if SIMULATE_DATA:
                system_status["connection"] = "SIMULATED"
            else:
                system_status["connection"] = "DISCONNECTED"
            time.sleep(3.0)


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.route('/')
def index():
    """Serves the main IoT control dashboard."""
    return render_template('index.html')

@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Returns the absolute latest sensor reading."""
    # Ensure system_status has dynamic values
    response_data = {
        "status": "SUCCESS",
        "connection": system_status["connection"],
        "com_port": system_status["com_port"],
        "total_readings": system_status["total_readings_logged"],
        "uptime_seconds": int(time.time() - system_status["uptime_start"]),
        "data": None
    }
    
    if system_status["last_reading"]:
        response_data["data"] = system_status["last_reading"]
        return jsonify(response_data)
    
    # Fallback to query DB if cache is empty
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                # Format timestamp
                if row["timestamp"]:
                    row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                response_data["data"] = row
        except Exception as e:
            print(f"[API /latest Exception] {e}")
        finally:
            cursor.close()
            conn.close()
            
    return jsonify(response_data)

@app.route('/api/history', methods=['GET'])
def get_history():
    """
    Returns the last N readings ordered ascending by timestamp
    for standard left-to-right rendering in Chart.js.
    """
    limit = request.args.get('limit', default=30, type=int)
    # Ensure safety limits
    limit = min(100, max(5, limit))
    
    data_points = []
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Subquery gets the latest rows, outer query orders them oldest-to-newest
            query = """
            SELECT * FROM (
                SELECT * FROM sensor_readings 
                ORDER BY timestamp DESC LIMIT %s
            ) AS sub 
            ORDER BY timestamp ASC
            """
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            for row in rows:
                if row["timestamp"]:
                    row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                data_points.append(row)
        except Exception as e:
            print(f"[API /history Exception] {e}")
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({
        "status": "SUCCESS",
        "count": len(data_points),
        "data": data_points
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Computes overall statistics: min, max, and avg for all metrics."""
    stats_data = {
        "temp": {"min": 0.0, "max": 0.0, "avg": 0.0},
        "humidity": {"min": 0.0, "max": 0.0, "avg": 0.0},
        "soil": {"min": 0.0, "max": 0.0, "avg": 0.0},
        "row_count": 0
    }
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            # Single composite stats query
            query = """
            SELECT 
                COUNT(*) as count,
                MIN(temp_c) as min_temp, MAX(temp_c) as max_temp, AVG(temp_c) as avg_temp,
                MIN(humidity_pct) as min_hum, MAX(humidity_pct) as max_hum, AVG(humidity_pct) as avg_hum,
                MIN(soil_pct) as min_soil, MAX(soil_pct) as max_soil, AVG(soil_pct) as avg_soil
            FROM sensor_readings
            """
            cursor.execute(query)
            row = cursor.fetchone()
            
            if row and row["count"] > 0:
                stats_data["row_count"] = row["count"]
                stats_data["temp"] = {
                    "min": round(row["min_temp"] or 0, 1),
                    "max": round(row["max_temp"] or 0, 1),
                    "avg": round(row["avg_temp"] or 0, 1)
                }
                stats_data["humidity"] = {
                    "min": round(row["min_hum"] or 0, 1),
                    "max": round(row["max_hum"] or 0, 1),
                    "avg": round(row["avg_hum"] or 0, 1)
                }
                stats_data["soil"] = {
                    "min": round(row["min_soil"] or 0, 1),
                    "max": round(row["max_soil"] or 0, 1),
                    "avg": round(row["avg_soil"] or 0, 1)
                }
        except Exception as e:
            print(f"[API /stats Exception] {e}")
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({
        "status": "SUCCESS",
        "stats": stats_data
    })

@app.route('/api/log', methods=['GET'])
def get_log():
    """Returns the most recent N rows in reverse chronological order for data logs."""
    limit = request.args.get('limit', default=20, type=int)
    limit = min(50, max(5, limit))
    
    logs = []
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            query = "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT %s"
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            for row in rows:
                if row["timestamp"]:
                    row["timestamp"] = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                logs.append(row)
        except Exception as e:
            print(f"[API /log Exception] {e}")
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({
        "status": "SUCCESS",
        "count": len(logs),
        "data": logs
    })

@app.route('/api/clear', methods=['POST'])
def clear_logs():
    """Utility endpoint to truncate logs and reset metrics for testing."""
    global system_status
    with db_lock:
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "ERROR", "message": "Database not reachable"}), 500
        
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE sensor_readings")
            conn.commit()
            system_status["total_readings_logged"] = 0
            system_status["last_reading"] = None
            return jsonify({"status": "SUCCESS", "message": "Database successfully cleared"})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500
        finally:
            cursor.close()
            conn.close()

# ==========================================
# SYSTEM RUN INITIALIZATION
# ==========================================
if __name__ == '__main__':
    print("=" * 60)
    print("      ROBOSENSE IoT ANALYTICS SYSTEM STARTUP")
    print("=" * 60)
    
    # 1. Initialize and verify database tables
    db_connected = bootstrap_database()
    
    # 2. Launch background serial monitor daemon thread
    bg_thread = threading.Thread(target=serial_reader_thread, daemon=True)
    bg_thread.start()
    
    # 3. Start web server on port 5000 (accessible locally)
    print("\n[Flask Server] Launching UI web interface on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
