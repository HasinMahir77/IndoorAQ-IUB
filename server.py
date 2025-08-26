from flask import Flask, request, jsonify, make_response
from flask_cors import CORS  # Import CORS
import sqlite3
from datetime import datetime
import pytz
import logging
import os
import csv
import io

script_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(script_dir, "sensor_data.db")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def setup_database():
    """Creates the SQLite table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deviceId INTEGER,
                timestamp TEXT,
                air_temperature REAL,
                humidity REAL,
                pressure REAL,
                altitude REAL,
                pm1 REAL,
                pm2_5 REAL,
                pm10 REAL,
                CO2 REAL
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Database setup complete.")
    except sqlite3.Error as e:
        logger.error(f"Error setting up database: {e}")

def save_to_db(payload):
    """Inserts data into the SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get timestamp in GMT+6 (Asia/Dhaka)
        tz = pytz.timezone("Asia/Dhaka")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        # Log the data
        formatted_data = (
            f"📡 Device {payload['deviceid']} Data Received:\n"
            f"   📅 Timestamp  : {timestamp}\n"
            f"   🌡 Temp       : {payload['air_temperature']}°C\n"
            f"   💧 Humidity   : {payload['humidity']}%\n"
            f"   🌍 Pressure   : {payload['pressure']} Pa\n"
            f"   🏔 Altitude   : {payload['altitude']} m\n"
            f"   🏭 PM1        : {payload['pm1']} µg/m³\n"
            f"   🏭 PM2.5      : {payload['pm2_5']} µg/m³\n"
            f"   🏭 PM10       : {payload['pm10']} µg/m³\n"
            f"   🏭 CO2        : {payload['co2']} ppm\n"
        )
        logger.info(formatted_data)

        # Insert into database
        cursor.execute("""
            INSERT INTO sensor_data (deviceId, timestamp, air_temperature, humidity, pressure, altitude, pm1, pm2_5, pm10, CO2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload["deviceid"], timestamp, payload["air_temperature"], payload["humidity"],
            payload["pressure"], payload["altitude"], payload["pm1"],
            payload["pm2_5"], payload["pm10"], payload["co2"]
        ))

        conn.commit()
        conn.close()
        logger.info("Data saved to database successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error saving data to database: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/cfd/data', methods=['POST'])
def receive_sensor_data():
    try:
        if request.is_json:
            data = request.get_json()

            # Map the keys from the received data to the expected format
            mapped_data = {
                "deviceid": data.get("deviceid"),
                "air_temperature": data.get("temp"),  # Map 'temp' to 'air_temperature'
                "humidity": data.get("hum"),  # Map 'hum' to 'humidity'
                "pressure": data.get("pressure"),
                "altitude": 10,  # Placeholder if no altitude data is sent
                "pm1": data.get("pm1"),
                "pm2_5": data.get("pm25"),  # Map 'pm25' to 'pm2_5'
                "pm10": data.get("pm10"),
                "co2": data.get("co2")
            }

            save_to_db(mapped_data)
            logger.info(f"Received JSON data: {mapped_data}")
            return jsonify({"status": "success", "message": "JSON received"}), 200
        else:
            logger.warning("Received non-JSON data.")
            return jsonify({"status": "error", "message": "Request must be JSON"}), 400
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/cfd/get-latest-all', methods=['GET'])
def get_latest_all():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Query to get the latest data for each unique deviceId, ordered by deviceId
        cursor.execute("""
            SELECT t1.*
            FROM sensor_data t1
            INNER JOIN (
                SELECT deviceId, MAX(timestamp) AS max_timestamp
                FROM sensor_data
                GROUP BY deviceId
            ) t2
            ON t1.deviceId = t2.deviceId AND t1.timestamp = t2.max_timestamp
            ORDER BY t1.deviceId
        """)
        rows = cursor.fetchall()
        conn.close()

        # Format the data into a list of dictionaries
        latest_data = [
            {
                "id": row[0],
                "deviceid": row[1],
                "timestamp": row[2],
                "air_temperature": row[3],
                "humidity": row[4],
                "pressure": row[5],
                "altitude": row[6],
                "pm1": row[7],
                "pm2_5": row[8],
                "pm10": row[9],
                "co2": row[10]
            }
            for row in rows
        ]

        return jsonify({"status": "success", "data": latest_data}), 200
    except sqlite3.Error as e:
        logger.error(f"Error retrieving latest data: {e}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/cfd/get-last-50/<string:deviceid>', methods=['GET'])
def get_last_10(deviceid):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Query the last 50 rows for the given deviceid, ordered by timestamp in descending order
        cursor.execute("""
            SELECT air_temperature, humidity, pressure, pm1, pm2_5, pm10, CO2, timestamp
            FROM sensor_data
            WHERE deviceId = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (deviceid,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "No data found for the given device ID"}), 404

        # Reverse the order to get the oldest first
        rows.reverse()

        # Separate the data into arrays for each metric
        temperatures = [row[0] for row in rows]
        humidities = [row[1] for row in rows]
        pressures = [row[2] for row in rows]
        pm1s = [row[3] for row in rows]
        pm25s = [row[4] for row in rows]
        pm10s = [row[5] for row in rows]
        co2s = [row[6] for row in rows]
        times = [datetime.strptime(row[7], "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p") for row in rows]

        return jsonify({
            "temperature": temperatures,
            "humidity": humidities,
            "pressure": pressures,
            "pm1": pm1s,
            "pm2_5": pm25s,
            "pm10": pm10s,
            "co2": co2s,
            "time": times
        }), 200
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/cfd/test', methods=['GET'])
def test_route():
    return "Server is online", 200

@app.route('/cfd/full/<string:deviceid>', methods=['GET'])
def download_device_data_csv(deviceid):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Query to get all data for the specific deviceId
        cursor.execute("""
            SELECT id, deviceId, timestamp, air_temperature, humidity, pressure, altitude, pm1, pm2_5, pm10, CO2
            FROM sensor_data
            WHERE deviceId = ?
            ORDER BY timestamp ASC
        """, (deviceid,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "No data found for the given device ID"}), 404

        # Create a CSV file in memory
        output = io.StringIO()
        csv_writer = csv.writer(output)

        # Write the CSV header
        csv_writer.writerow(["id", "deviceId", "timestamp", "air_temperature", "humidity", "pressure", "altitude", "pm1", "pm2_5", "pm10", "co2"])

        # Write the data to the CSV file
        for row in rows:
            csv_writer.writerow(row)

        # Create a response with the CSV content
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=device_{deviceid}_data.csv'
        response.mimetype = 'text/csv'

        logger.info(f"CSV download requested for device {deviceid} - {len(rows)} rows exported")
        return response
    except sqlite3.Error as e:
        logger.error(f"Error retrieving data for device {deviceid}: {e}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == '__main__':
    setup_database()
    app.run(port=7000)
