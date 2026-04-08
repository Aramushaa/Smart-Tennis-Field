# env vars
import os
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Multiple subscriptions (comma-separated)
SUB_TOPICS = os.getenv(
    "SUB_TOPICS",
    "tennis/sensor/+/events,tennis/camera/+/ball"
)
SUB_TOPICS = [t.strip() for t in SUB_TOPICS.split(",") if t.strip()]

# Optional: publishing via /publish endpoint
PUB_TOPIC = os.getenv("PUB_TOPIC", "tennis/sensor/1/events")

EVENT_BUFFER_MAX = int(os.getenv("EVENT_BUFFER_MAX", "100"))

INFLUX_WRITE_GENERIC_EVENTS = os.getenv("INFLUX_WRITE_GENERIC_EVENTS", "1") == "1"

INFLUX_ENABLED = os.getenv("INFLUX_ENABLED", "0") == "1"
INFLUX_HOST = os.getenv("INFLUX_HOST", "http://localhost:8181")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_DATABASE = os.getenv("INFLUX_DATABASE", "tennis")
INFLUX_TABLE = os.getenv("INFLUX_TABLE", "events")
INFLUX_IMU_TABLE = os.getenv("INFLUX_IMU_TABLE", "imu_raw")
INFLUX_BATCH_SIZE = int(os.getenv("INFLUX_BATCH_SIZE", "500"))
INFLUX_FLUSH_INTERVAL_MS = int(os.getenv("INFLUX_FLUSH_INTERVAL_MS", "200"))
