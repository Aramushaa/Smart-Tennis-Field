import time
from app.metawear_client import MetaWearClient
from app.mqtt_publisher import MQTTPublisher
from app.config import MAC_ADDRESS, MQTT_TOPIC, DEVICE_NAME, RECORDING_ID

if not MAC_ADDRESS or MAC_ADDRESS == "YOUR_MAC_ADDRESS_HERE":
    raise RuntimeError("Set METAWEAR_MAC_ADDRESS in .env before starting the bridge")

publisher = MQTTPublisher()

latest_acc = None
latest_gyro = None
sample_idx = 0
recording_started_at = time.time()
session_recording_id = f"{RECORDING_ID}_{time.strftime('%Y%m%d_%H%M%S')}"


def publish_if_ready():
    global latest_acc, latest_gyro, sample_idx

    if latest_acc is None or latest_gyro is None:
        return

    dataset_ts = time.time() - recording_started_at

    payload = {
        "source": "metawear",
        "device": DEVICE_NAME,
        "recording_id": session_recording_id,
        "dataset_ts": dataset_ts,
        "sample_idx": sample_idx,
        "acc_x": latest_acc[0],
        "acc_y": latest_acc[1],
        "acc_z": latest_acc[2],
        "gyro_x": latest_gyro[0],
        "gyro_y": latest_gyro[1],
        "gyro_z": latest_gyro[2],
        "activity_gt": "unknown",
    }

    publisher.publish(MQTT_TOPIC, payload)
    sample_idx += 1


def my_function(sensor, timestamp, x, y, z):
    global latest_acc, latest_gyro

    if sensor == "acc":
        latest_acc = (x, y, z)
        return
    elif sensor == "gyro":
        latest_gyro = (x, y, z)

    publish_if_ready()


sensor = MetaWearClient(MAC_ADDRESS)
sensor.set_callback(my_function)

print("Connecting to MetaWear...")
print(f"Recording id: {session_recording_id}")
sensor.connect()
sensor.configure()
print("Streaming to MQTT...")
sensor.start_sampling()

while True:
    time.sleep(1)
