# Siddha Dataset Contract

## Purpose
This document defines how Siddha dataset rows are mapped into MQTT events and InfluxDB points.

## Source columns
- device
- activity
- id
- gyro_x
- gyro_y
- gyro_z
- acc_x
- acc_y
- acc_z
- timestamp

## Column meaning
- device: sensor source type or acquisition device (example: phone)
- activity: ground-truth activity label from dataset
- id: recording/session identifier
- gyro_x, gyro_y, gyro_z: gyroscope readings on 3 axes
- acc_x, acc_y, acc_z: accelerometer readings on 3 axes
- timestamp: relative dataset timestamp inside the recording

## MQTT topic mapping
Recommended topic:
tennis/sensor/<device>/events

Example:
tennis/sensor/phone/events

## MQTT payload mapping
Example JSON payload:
{
  "device": "phone",
  "recording_id": "48",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "acc_x": -0.029474,
  "acc_y": -0.186824,
  "acc_z": -0.06387,
  "gyro_x": -0.571848,
  "gyro_y": 3.644636,
  "gyro_z": -9.897467,
  "ts": "2026-03-23T10:00:00Z"
}

## InfluxDB mapping

### Measurement
imu_raw

### Tags
- device
- recording_id

### Fields
- activity_gt
- dataset_ts
- acc_x
- acc_y
- acc_z
- gyro_x
- gyro_y
- gyro_z

### Influx timestamp
Replay wall-clock publish time from the simulator.

## Notes
- dataset_ts preserves original dataset timing
- ts preserves actual event creation time in the simulator
- activity_gt is the dataset label, not the predicted HAR output