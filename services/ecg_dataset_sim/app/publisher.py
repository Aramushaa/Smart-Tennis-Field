from __future__ import annotations

import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from .dataset_loader import EcgSample


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MqttPublisher:
    def __init__(self, host: str, port: int, topic: str, qos: int):
        self.host = host
        self.port = port
        self.topic = topic
        self.qos = qos
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self) -> None:
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def build_payload(self, sample: EcgSample) -> dict:
        return {
            "source": sample.source,
            "device": sample.device,
            "subject": sample.subject,
            "task": sample.task,
            "recording_id": sample.recording_id,
            "sensor_ts": sample.sensor_ts,
            "sample_idx": sample.sample_idx,
            "sampling_rate_hz": sample.sampling_rate_hz,
            "ecg_value": sample.ecg_value,
            "unit": sample.unit,
            "ts": now_iso(),
        }

    def publish_sample(self, sample: EcgSample) -> None:
        result = self.client.publish(
            topic=self.topic,
            payload=json.dumps(self.build_payload(sample)),
            qos=self.qos,
        )
        result.wait_for_publish()
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Failed to publish ECG sample, rc={result.rc}")
