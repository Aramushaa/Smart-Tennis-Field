import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


DATASET_PATH = os.getenv("ECG_DATASET_PATH", "/app/dataset/openneuro_ds006848")
SUBJECT = os.getenv("ECG_SUBJECT", "sub-001")
TASK = os.getenv("ECG_TASK", "verbalwm")
MAX_SECONDS = _float_env("ECG_MAX_SECONDS", 30.0)
REPLAY_SPEED = _float_env("ECG_REPLAY_SPEED", 1.0)
STARTUP_DELAY_SECONDS = _float_env("ECG_STARTUP_DELAY_SECONDS", 5.0)
DOWNSAMPLE_HZ = _float_env("ECG_DOWNSAMPLE_HZ", 100.0)

MQTT_HOST = os.getenv("ECG_MQTT_HOST", "emqx")
MQTT_PORT = _int_env("ECG_MQTT_PORT", 1883)
RAW_TOPIC = os.getenv("ECG_RAW_TOPIC", "tennis/ecg/raw")
MQTT_QOS = _int_env("ECG_MQTT_QOS", 1)
