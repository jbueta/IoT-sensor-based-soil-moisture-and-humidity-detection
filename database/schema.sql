-- RoboSense MySQL database schema
-- Project guideline note:
-- The original requirement references SQLite/CSV storage. This implementation
-- uses MySQL as the persistent database layer for sensor readings.

CREATE DATABASE IF NOT EXISTS robosense_db;

USE robosense_db;

CREATE TABLE IF NOT EXISTS sensor_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    temp_c FLOAT,
    humidity_pct FLOAT,
    soil_pct FLOAT,
    status VARCHAR(20),
    flag VARCHAR(10)
);
