from __future__ import annotations

from .config import settings
from .influx import escape_string_field, escape_tag_value, write_line_protocol


def build_prediction_line(
    *,
    device: str,
    recording_id: str,
    prediction: str,
    confidence: float,
    metadata: dict,
) -> str:
    # DB-polling mode uses the dataset-relative timestamp for reproducible evaluation.
    # MQTT live mode passes prediction_epoch_ns so Grafana can show predictions in real time.
    point_ts = int(
        metadata.get(
            "prediction_epoch_ns",
            int(float(metadata["end_dataset_ts"]) * 1_000_000_000),
        )
    )

    return (
        f"{settings.prediction_table},"
        f"device={escape_tag_value(device)},"
        f"recording_id={escape_tag_value(recording_id)},"
        f"model_name={escape_tag_value(settings.model_name)},"
        f"input_layout={escape_tag_value(settings.input_layout)},"
        f"score_aggregation={escape_tag_value(settings.score_aggregation)} "
        f'predicted_label="{escape_string_field(prediction)}",'
        f'activity_gt="{escape_string_field(metadata["activity_gt"])}",'
        f"confidence={confidence},"
        f'window_start_dataset_ts={metadata["start_dataset_ts"]},'
        f'window_end_dataset_ts={metadata["end_dataset_ts"]},'
        f'window_size={metadata["window_size"]}i,'
        f'window_stride={settings.window_stride}i '
        f"{point_ts}"
    )


def write_prediction_point(
    *,
    device: str,
    recording_id: str,
    prediction: str,
    confidence: float,
    metadata: dict,
) -> None:
    write_line_protocol(
        build_prediction_line(
            device=device,
            recording_id=recording_id,
            prediction=prediction,
            confidence=confidence,
            metadata=metadata,
        )
    )
