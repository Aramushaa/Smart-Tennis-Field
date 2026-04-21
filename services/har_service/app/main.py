from __future__ import annotations

import logging
import time

from .config import settings
from .inference_adapter import HarInferenceAdapter
from .influx import query_influx_sql
from .windowing import (
    build_sliding_windows,
    group_rows_by_device_and_recording,
    window_to_model_input,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def fetch_ordered_imu_rows(limit: int) -> list[dict]:
    where_clauses = []

    if settings.filter_device:
        where_clauses.append(f"device = '{settings.filter_device}'")

    if settings.filter_recording_id:
        where_clauses.append(f"recording_id = '{settings.filter_recording_id}'")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
    SELECT
        time,
        device,
        recording_id,
        sample_idx,
        activity_gt,
        dataset_ts,
        acc_x,
        acc_y,
        acc_z,
        gyro_x,
        gyro_y,
        gyro_z
    FROM {settings.imu_table}
    {where_sql}
    ORDER BY device ASC, recording_id ASC, time ASC, sample_idx ASC
    LIMIT {limit}
    """.strip()

    return query_influx_sql(sql)

def log_window_summary(
    device: str,
    recording_id: str,
    windows: list[list[dict]],
) -> None:
    if not windows:
        logger.info(
            "No complete windows | device=%s | recording_id=%s",
            device,
            recording_id,
        )
        return

    first_window = windows[0]
    first_row = first_window[0]
    last_row = first_window[-1]

    logger.info(
        "Built %s windows | device=%s | recording_id=%s | first_window_size=%s | first_dataset_ts=%s | last_dataset_ts=%s",
        len(windows),
        device,
        recording_id,
        len(first_window),
        first_row.get("dataset_ts"),
        last_row.get("dataset_ts"),
    )

def evaluate_windows_for_stream(
    device: str,
    recording_id: str,
    windows: list[list[dict]],
    inference,
    max_windows: int,
) -> None:
    if not windows:
        logger.info(
            "No windows to evaluate | device=%s | recording_id=%s",
            device,
            recording_id,
        )
        return

    predicted_counts: dict[str, int] = {}

    windows_to_check = windows[:max_windows]
    skipped_windows = max(0, len(windows) - len(windows_to_check))

    logger.info(
        "Window coverage | device=%s | recording_id=%s | total_windows=%s | checked_windows=%s | skipped_windows=%s | max_windows=%s",
        device,
        recording_id,
        len(windows),
        len(windows_to_check),
        skipped_windows,
        max_windows,
    )

    for idx, window in enumerate(windows_to_check):
        model_input = window_to_model_input(window)
        prediction_details = inference.predict_details(model_input)
        prediction = prediction_details["predicted_label"]

        predicted_counts[prediction] = predicted_counts.get(prediction, 0) + 1

        logger.info(
            "Window prediction | device=%s | recording_id=%s | window_idx=%s | activity_gt=%s | predicted=%s | confidence=%.2f | top_k=%s | start_dataset_ts=%s | end_dataset_ts=%s",
            model_input["metadata"]["device"],
            model_input["metadata"]["recording_id"],
            idx,
            model_input["metadata"]["activity_gt"],
            prediction,
            prediction_details["confidence"],
            prediction_details["top_k"],
            model_input["metadata"]["start_dataset_ts"],
            model_input["metadata"]["end_dataset_ts"],
        )

    logger.info(
        "Prediction summary | device=%s | recording_id=%s | total_windows=%s | checked_windows=%s | skipped_windows=%s | predicted_counts=%s",
        device,
        recording_id,
        len(windows),
        len(windows_to_check),
        skipped_windows,
        predicted_counts,
    )


def main() -> None:
    logger.info("Starting %s", settings.service_name)
    logger.info(
        "Configuration | influx_database=%s | imu_table=%s | query_limit=%s | window_size=%s | window_stride=%s | model_path=%s | labels_path=%s",
        settings.influx_database,
        settings.imu_table,
        settings.query_limit,
        settings.window_size,
        settings.window_stride,
        settings.model_path,
        settings.labels_path,
    )

    inference = HarInferenceAdapter(
        model_path=settings.model_path,
        labels_path=settings.labels_path,
        debug=settings.debug_inference,
        top_k=settings.prediction_top_k,
        input_layout=settings.input_layout,
        temporal_preprocess=settings.temporal_preprocess,
        score_aggregation=settings.score_aggregation,
    )
    logger.info("Inference engine initialized successfully")

    try:
        while True:
            try:
                rows = fetch_ordered_imu_rows(settings.query_limit)
                logger.info("Fetched %s ordered IMU rows from %s", len(rows), settings.imu_table)

                if not rows:
                    logger.info("No rows fetched from %s", settings.imu_table)
                    time.sleep(settings.poll_interval_seconds)
                    continue

                groups = group_rows_by_device_and_recording(rows)
                logger.info("Grouped rows into %s streams", len(groups))

                total_windows = 0

                for (device, recording_id), group_rows in groups.items():
                    windows = build_sliding_windows(
                        rows=group_rows,
                        window_size=settings.window_size,
                        stride=settings.window_stride,
                    )

                    evaluate_windows_for_stream(
                        device=device,
                        recording_id=recording_id,
                        windows=windows,
                        inference=inference,
                        max_windows=settings.max_windows_per_stream,
                    )

                    total_windows += len(windows)
                    log_window_summary(device, recording_id, windows)

                logger.info("Total windows built in this cycle: %s", total_windows)

            except Exception:
                logger.exception("HAR cycle failed")

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        logger.warning("%s interrupted by user", settings.service_name)


if __name__ == "__main__":
    main()
