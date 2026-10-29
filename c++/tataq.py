import json
import random
import time
import ssl
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from threading import Event

# ==========================================
# 1. HIVEMQ CLOUD CONFIGURATION
# ==========================================

# FIX: Remove the port (:8883) from the broker hostname string
BROKER = "eb858dac581b481ca7cdf8252b087756.s1.eu.hivemq.cloud"
PORT = 8883

USERNAME = "xyz"
PASSWORD = "12345678"

TOPIC = "mait/motor/MOTOR_PUMP_01/telemetry"

CLIENT_ID = "MAIT_Motor_Publisher_01"

connected = Event()

# ==========================================
# 2. MQTT CALLBACK FUNCTIONS
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("\nSuccessfully connected to HiveMQ Cloud!")
        print("Broker:", BROKER)
        print("Topic:", TOPIC)
        connected.set()
    else:
        print("Connection failed with reason code:", reason_code)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    connected.clear()
    print("Disconnected from HiveMQ.")


# ==========================================
# 3. CREATE MQTT CLIENT
# ==========================================

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=CLIENT_ID,
    protocol=mqtt.MQTTv311
)

# Authentication
client.username_pw_set(USERNAME, PASSWORD)

# Secure TLS connection (HiveMQ Cloud default)
client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

# Assign callbacks
client.on_connect = on_connect
client.on_disconnect = on_disconnect


# ==========================================
# 4. MOTOR SENSOR SIMULATION
# ==========================================

baseline_temp = 50.0
baseline_vib = 1.5
baseline_current = 12.5

degradation = 0.0
reading_number = 0


def generate_motor_data():
    global degradation, reading_number

    reading_number += 1
    degradation += 0.05

    vibration = round(
        baseline_vib + degradation * 0.2 + random.gauss(0, 0.1), 2
    )
    temperature = round(
        baseline_temp + degradation * 0.8 + random.gauss(0, 0.3), 2
    )
    current = round(
        baseline_current + random.gauss(0, 0.2), 2
    )

    if vibration > 4.5 or temperature > 85:
        status = "CRITICAL"
    elif vibration > 3.0 or temperature > 70:
        status = "WARNING"
    else:
        status = "HEALTHY"

    payload = {
        "machine_id": "MOTOR_PUMP_01",
        "reading_number": reading_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "telemetry": {
            "vibration_rms": vibration,
            "temperature": temperature,
            "current": current
        },
        "status": status
    }

    return payload


# ==========================================
# 5. CONNECT AND PUBLISH DATA
# ==========================================

try:
    print("Connecting to HiveMQ Cloud...")
    client.connect(BROKER, PORT, keepalive=60)

    # Start network loop
    client.loop_start()

    # Wait for successful connection
    if not connected.wait(timeout=20):
        raise TimeoutError(
            "HiveMQ connection timed out. Check credentials and hostname."
        )

    print("\nStarting motor telemetry publishing...")
    print("Press Ctrl + C to stop.\n")

    while True:
        motor_data = generate_motor_data()
        message = json.dumps(motor_data)

        result = client.publish(
            TOPIC,
            message,
            qos=1,
            retain=False
        )

        result.wait_for_publish(timeout=10)

        if result.is_published():
            print("-----------------------------------")
            print("Reading:", motor_data["reading_number"])
            print("Temperature:", motor_data["telemetry"]["temperature"], "°C")
            print("Vibration:", motor_data["telemetry"]["vibration_rms"], "mm/s")
            print("Current:", motor_data["telemetry"]["current"], "A")
            print("Status:", motor_data["status"])
            print("MQTT Publish: SUCCESS")
        else:
            print("Message was not confirmed as published.")

        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopping motor monitoring...")

except Exception as error:
    print("\nError:", error)

finally:
    client.loop_stop()
    client.disconnect()
    print("MQTT connection closed.")