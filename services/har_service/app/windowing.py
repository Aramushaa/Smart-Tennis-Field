from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Iterable


def group_rows_by_device_and_recording(rows: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    """
    Group rows by logical signal stream:
    (device, recording_id)

    Why:
    - prevents mixing unrelated sequences
    - preserves thesis-defensible HAR boundaries
    """
    groups: DefaultDict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in rows:
        device = str(row.get("device", "unknown"))
        recording_id = str(row.get("recording_id", "unknown"))
        groups[(device, recording_id)].append(row)

    return dict(groups)


def build_sliding_windows(
    rows: list[dict],
    window_size: int,
    stride: int,
) -> list[list[dict]]:
    """
    Build overlapping sliding windows from a single ordered row sequence.

    Assumptions:
    - rows belong to the same (device, recording_id)
    - rows are already ordered in ascending time
    """
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if stride <= 0:
        raise ValueError("stride must be > 0")

    windows: list[list[dict]] = []

    if len(rows) < window_size:
        return windows

    for start in range(0, len(rows) - window_size + 1, stride):
        end = start + window_size
        windows.append(rows[start:end])

    return windows