import json
import paho.mqtt.client as mqtt
from app.config import MQTT_HOST, MQTT_PORT


class MQTTPublisher:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.client.loop_start()

    def publish(self, topic, payload):
        result = self.client.publish(topic, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Failed to publish MQTT message to {topic}: rc={result.rc}"
            )
