import os

from dotenv import load_dotenv

load_dotenv()

MAC_ADDRESS = os.getenv("METAWEAR_MAC_ADDRESS", "")
DEVICE_NAME = os.getenv("METAWEAR_DEVICE_NAME", "watch")
RECORDING_ID = os.getenv("METAWEAR_RECORDING_ID", "real_metawear_session_001")

MQTT_HOST = os.getenv("METAWEAR_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("METAWEAR_MQTT_PORT", "2883"))
MQTT_TOPIC = os.getenv("METAWEAR_MQTT_TOPIC", "tennis/sensor/watch/events")
