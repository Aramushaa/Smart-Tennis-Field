from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    service_name: str = "har-service"
    poll_interval_seconds: float = 5.0

    influx_host: str = "http://influxdb3:8181"
    influx_token: str = ""
    influx_database: str = "tennis"

    imu_table: str = "imu_raw_full_rows"
    prediction_table: str = "har_predictions_7_activity"

    model_path: str = "/app/model/L2MU_plain_leaky.onnx"
    labels_path: str = "/app/model/labels.txt"

    model_name: str = "L2MU_plain_leaky"
    input_layout: str = "gyro_then_accel"
    score_aggregation: str = "sum"

    window_size: int = 40
    window_stride: int = 20
    max_windows_per_stream: int = 10
    query_limit: int = 5000
    prediction_top_k: int = 3
    debug_inference: bool = False
    temporal_preprocess: str = "none"

    filter_device: str | None = None
    filter_recording_id: str | None = None
    allowed_activity_gt: str = "F,G,O,P,Q,R,S"

    @property
    def allowed_activity_codes(self) -> list[str]:
        return [
            item.strip()
            for item in self.allowed_activity_gt.split(",")
            if item.strip()
        ]

    model_config = SettingsConfigDict(
        env_prefix="HAR_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
