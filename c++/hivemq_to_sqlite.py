
import json
import sqlite3
import ssl
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# ==========================================
# 1. HIVEMQ CLOUD CONFIGURATION
# ==========================================

BROKER = "eb858dac581b481ca7cdf8252b087756.s1.eu.hivemq.cloud"
PORT = 8883

# Use your actual HiveMQ Cloud credentials locally.
USERNAME = "xyz"
PASSWORD = "12345678"

TOPIC = "mait/motor/MOTOR_PUMP_01/telemetry"
CLIENT_ID = "MAIT_Motor_SQLite_Subscriber"

DB_NAME = "motor_data.db"


# ==========================================
# 2. CREATE SQLITE DATABASE
# ==========================================

def create_database():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS motor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            reading_number INTEGER,
            timestamp TEXT,
            temperature REAL,
            vibration_rms REAL,
            current REAL,
            status TEXT,
            received_at TEXT,
            raw_json TEXT
        )
    """)

    conn.commit()
    conn.close()

    print("SQLite database and table are ready.")


# ==========================================
# 3. CONNECT TO SQLITE AND SAVE DATA
# ==========================================

def save_to_sqlite(payload):
    telemetry = payload["telemetry"]

    conn = sqlite3.connect(DB_NAME)

    try:
        conn.execute("""
            INSERT INTO motor_data (
                machine_id,
                reading_number,
                timestamp,
                temperature,
                vibration_rms,
                current,
                status,
                received_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.get("machine_id"),
            payload.get("reading_number"),
            payload.get("timestamp"),
            telemetry.get("temperature"),
            telemetry.get("vibration_rms"),
            telemetry.get("current"),
            payload.get("status"),
            datetime.now(timezone.utc).isoformat(),
            json.dumps(payload)
        ))

        conn.commit()

    finally:
        conn.close()


# ==========================================
# 4. MQTT CALLBACKS
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to HiveMQ Cloud successfully!")
        client.subscribe(TOPIC, qos=1)
        print("Subscribed to:", TOPIC)
    else:
        print("Connection failed:", reason_code)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        save_to_sqlite(payload)

        telemetry = payload["telemetry"]

        print("-----------------------------------")
        print("Machine:", payload.get("machine_id"))
        print("Reading:", payload.get("reading_number"))
        print("Temperature:", telemetry.get("temperature"), "°C")
        print("Vibration:", telemetry.get("vibration_rms"), "mm/s")
        print("Current:", telemetry.get("current"), "A")
        print("Status:", payload.get("status"))
        print("Saved to SQLite successfully!")

    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as error:
        print("Invalid telemetry message:", error)

    except sqlite3.Error as error:
        print("SQLite database error:", error)


# ==========================================
# 5. START SUBSCRIBER
# ==========================================

if __name__ == "__main__":
    create_database()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311
    )

    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("Connecting to HiveMQ Cloud...")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever()

    except KeyboardInterrupt:
        print("\nStopping SQLite subscriber...")

    except (OSError, ValueError) as error:
        print("Connection error:", error)

    finally:
        client.disconnect()
        print("Subscriber stopped.")
