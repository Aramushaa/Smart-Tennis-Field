from fastapi import APIRouter
from ..config import INFLUX_ENABLED

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ingest-service",
        "influx_enabled": INFLUX_ENABLED,
    }