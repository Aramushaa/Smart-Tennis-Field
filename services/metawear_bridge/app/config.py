import os
from dotenv import load_dotenv

load_dotenv()

MAC_ADDRESS = os.getenv("METAWEAR_MAC_ADDRESS", "")
DEVICE_NAME = os.getenv("METAWEAR_DEVICE_NAME", "watch")
RECORDING_ID = os.getenv("METAWEAR_RECORDING_ID", "real_metawear_session_001")
SAMPLING_RATE_HZ = float(os.getenv("METAWEAR_SAMPLING_RATE_HZ", "25"))

# The bridge runs locally on the host for BLE access, so it normally uses the
# host-mapped EMQX port: localhost:2883 -> container:1883.
MQTT_HOST = os.getenv("METAWEAR_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("METAWEAR_MQTT_PORT", "2883"))

# Phase 4 architecture: bridge publishes RAW per-sensor events.
# A cleaner service converts them into canonical IMU rows.
MQTT_TOPIC = os.getenv("METAWEAR_MQTT_TOPIC", "tennis/watch/raw")
