import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


DATASET_PATH = os.getenv("EEG_DATASET_PATH", "/app/dataset/openneuro_ds006848")
SUBJECT = os.getenv("EEG_SUBJECT", "sub-001")
TASK = os.getenv("EEG_TASK", "verbalwm")
MAX_SECONDS = _float_env("EEG_MAX_SECONDS", 30.0)
REPLAY_SPEED = _float_env("EEG_REPLAY_SPEED", 1.0)
CHANNEL_LIMIT = _int_env("EEG_CHANNEL_LIMIT", 8)
DOWNSAMPLE_HZ = _float_env("EEG_DOWNSAMPLE_HZ", 100.0)

MQTT_HOST = os.getenv("EEG_MQTT_HOST", "emqx")
MQTT_PORT = _int_env("EEG_MQTT_PORT", 1883)
RAW_TOPIC = os.getenv("EEG_RAW_TOPIC", "tennis/eeg/raw")
MQTT_QOS = _int_env("EEG_MQTT_QOS", 1)
