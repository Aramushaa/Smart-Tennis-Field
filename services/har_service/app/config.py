from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "har-service"
    poll_interval_seconds: float = 5.0

    influx_host: str = "http://influxdb3:8181"
    influx_token: str = ""
    influx_database: str = "Siddha_full"

    imu_table: str = "imu_raw"
    prediction_table: str = "har_predictions"

    model_path: str = "/app/model/L2MU_plain_leaky.onnx"
    labels_path: str = "/app/model/labels.txt"

    query_limit: int = 5000
    window_size: int = 40
    window_stride: int = 20
    max_windows_per_stream: int = 10
    prediction_top_k: int = 3
    debug_inference: bool = False
    input_layout: str = "accel_then_gyro"
    temporal_preprocess: str = "none"
    score_aggregation: str = "sum"

    filter_device: str | None = None
    filter_recording_id: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="HAR_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
