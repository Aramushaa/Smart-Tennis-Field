from datetime import datetime
from fastapi import HTTPException


def validate_iso_timestamp(value: str, name: str) -> str:
    """
    Validate and normalize an ISO-8601 timestamp.
    """
    try:
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.isoformat()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timestamp for '{name}': {value!r}. Expected ISO-8601 format.",
        )