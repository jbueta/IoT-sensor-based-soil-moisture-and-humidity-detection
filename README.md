# IoT Robo-System Sensor Data Monitoring Web Application

A full-stack, real-time IoT environmental monitoring and analytics dashboard built using **Python Flask**, **MySQL**, **pyserial**, and **Chart.js**.

This system captures climatic values (Temperature, Humidity, Soil Moisture) from an Arduino Uno via an HC-05 Bluetooth transceiver, processes and stores them inside a persistent MySQL database, and serves a premium light-mode analytical dashboard on standard local web browsers.

---

## System Architecture
```
Soil Moisture Sensor + DHT11 (Temp/Humidity) + RGB LED
                        ↓
                  Arduino Uno
                        ↓
            HC-05 Bluetooth Module
                        ↓
            Python Backend (Flask + pyserial)
                        ↓
                  MySQL Database
                        ↓
            Web Dashboard (HTML5/CSS3/JS + Chart.js)
```

---

## Core Visual Features
1. **Dynamic Design System:** Highly premium light-mode layout using Google Font `IBM Plex Sans` for general labels, and `IBM Plex Mono` for raw data readouts and database records.
2. **Glowing State Banner:** pulsing color-coded status bar indicating active environmental alerts (Green = Optimal, Amber = Temperature Warning, Red = Soil Dry Danger).
3. **SVG Circle Gauge:** Custom circular rendering for soil moisture percentages.
4. **Delta Trend Calculations:** Real-time direction badges showing whether readings are rising (`▲`), falling (`▼`), or remaining stable (`──`).
5. **Interactive Chart.js Trends:** Dynamic line graphs showing recent history, with a red warning dotted threshold line at 30°C on the temperature tab.
6. **Live MySQL Logging Grid:** Live-scrolling tabular logs displaying rows matching `sensor_readings` table, with alert warning and critical cells colored.

---

## Hardware Configuration (Arduino Side)
* **Serial Baud Rate:** `9600`
* **Sampling Rate:** Every 2 seconds
* **Ingestion string format:** `TEMP=27.4;HUM=68;SOIL=75`
* **Status Logic (RGB LED):**
  * **Red Light:** Soil moisture < 20% (CRITICAL DRY)
  * **Orange/Amber Light:** Temperature > 30°C (WARN TEMP)
  * **Green Light:** Parameters within safe normal range (OPTIMAL)

---

## Tech Stack & Dependencies
* **Backend:** Python 3, Flask, pyserial, mysql-connector-python
* **Database:** MySQL (installed via XAMPP or separate engine)
* **Frontend:** HTML5, Vanilla CSS3, JavaScript (ES6+), Chart.js via CDN

---

## Installation & Setup

### 1. Start MySQL Server
Ensure MySQL is active in your XAMPP Control Panel (or default local instance on Port `3306`).
* *Note: The Python backend automatically handles creating the database `robosense_db` and its table `sensor_readings` on startup. You do not need to create them manually!*

### 2. Configure Settings (Optional)
Open [app.py](file:///D:/xampp_latest/htdocs/IoT/app.py) in your editor and adjust configuration constants at the top:
```python
COM_PORT = "COM3"          # Your HC-05 Bluetooth serial COM Port
BAUD_RATE = 9600

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = ""               # Default empty for XAMPP
DB_NAME = "robosense_db"
```

### 3. Install Dependencies
Run the following command in your terminal to download and configure requirements:
```bash
pip install -r requirements.txt
```

### 4. Run the Server
Launch the Flask development server:
```bash
python app.py
```

### 5. Open the Dashboard
Navigate your browser to:
[http://localhost:5000](http://localhost:5000)

### 6. Git Branching & Remote Setup
The local repository has been initialized and fully committed on a dedicated branch:
* **Proposed Repository Name:** `IoT-sensor-based-soil-moisture-and-humidity-detection`
* **Default Branch:** `main`
* **Working Branch:** `staging`

To link this local workspace to your GitHub repository and push the initial commit:
```bash
# 1. Add your remote repository URL (GitHub/GitLab staging)
git remote add origin https://github.com/jbueta/IoT-sensor-based-soil-moisture-and-humidity-detection.git

# 2. Push the default branch first (this sets main as the default on GitHub)
git push -u origin main

# 3. Push the staging branch next
git push -u origin staging
```

---

## Intelligent Simulator Fallback Mode
If you do not have physical Arduino hardware connected or the designated `COM3` port is not currently connected to your computer:
* **The system will automatically switch to Simulated Fallback Mode.**
* It will generate high-fidelity, drifting climatic sensor logs to mock realistic weather/moisture progressions.
* These simulated records are automatically inserted into MySQL every 2 seconds, allowing you to fully interact with charts, statistics, logs, and delta trends out-of-the-box!
