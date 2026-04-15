from __future__ import annotations

import logging
import time

from .config import settings
from .influx import query_influx_sql
from .windowing import (
    build_sliding_windows,
    group_rows_by_device_and_recording,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def fetch_ordered_imu_rows(limit: int) -> list[dict]:
    """
    Fetch IMU rows in deterministic order for window construction.

    ORDER BY device, recording_id, time ASC
    makes sequence grouping easier and defensible.
    """
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
    ORDER BY device ASC, recording_id ASC, time ASC
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


def main() -> None:
    logger.info("Starting %s", settings.service_name)
    logger.info(
        "Configuration | influx_database=%s | imu_table=%s | query_limit=%s | window_size=%s | window_stride=%s",
        settings.influx_database,
        settings.imu_table,
        settings.query_limit,
        settings.window_size,
        settings.window_stride,
    )

    try:
        while True:
            rows = fetch_ordered_imu_rows(settings.query_limit)
            logger.info("Fetched %s ordered IMU rows from %s", len(rows), settings.imu_table)

            groups = group_rows_by_device_and_recording(rows)
            logger.info("Grouped rows into %s streams", len(groups))

            total_windows = 0

            for (device, recording_id), group_rows in groups.items():
                windows = build_sliding_windows(
                    rows=group_rows,
                    window_size=settings.window_size,
                    stride=settings.window_stride,
                )
                total_windows += len(windows)
                log_window_summary(device, recording_id, windows)

            logger.info("Total windows built in this cycle: %s", total_windows)

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        logger.warning("%s interrupted by user", settings.service_name)


if __name__ == "__main__":
    main()