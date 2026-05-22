# Database Setup

This project uses **MySQL** as the persistent data storage layer for sensor readings.

The project guideline references SQLite database or CSV file storage. For this implementation, MySQL is used instead of SQLite because the system is intended to run with XAMPP MySQL. CSV export remains available as a reporting feature, but MySQL is the primary database.

## Database Artifact

The schema file is:

```text
database/schema.sql
```

It creates:

- database: `robosense_db`
- table: `sensor_readings`

The table stores:

- `id`
- `timestamp`
- `temp_c`
- `humidity_pct`
- `soil_pct`
- `status`
- `flag`

## Automatic Setup

The Flask application also creates the database and table automatically during startup through `app.py`.

Run the app from the project root:

```powershell
python app.py
```

If XAMPP MySQL is running and the configured user has permission, the app verifies or creates `robosense_db.sensor_readings` automatically.

## Manual Setup

Use manual setup if you want to prepare the database before running the app.

### phpMyAdmin

1. Start MySQL in XAMPP Control Panel.
2. Open phpMyAdmin.
3. Import `database/schema.sql`.

### MySQL CLI

From the project root:

```powershell
mysql -u root < database/schema.sql
```

If your MySQL root user has a password:

```powershell
mysql -u root -p < database/schema.sql
```

## Verification

After running the application, verify stored records with:

```sql
USE robosense_db;
SELECT COUNT(*) FROM sensor_readings;
SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 5;
```
