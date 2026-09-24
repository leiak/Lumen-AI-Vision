from pydantic_settings import BaseSettings


class EdgeSettings(BaseSettings):
    camera_id: str
    area_id: str
    video_source: str
    model_path: str = "yolov8n.pt"
    api_base_url: str = "http://localhost:8000"
    api_key: str = "edge-dev-key"
    stay_threshold_seconds: int = 300
    high_risk_seconds: int = 600
    keyframe_interval_seconds: int = 10
    area_polygon: list[list[int]] = [[0, 0], [1, 0], [1, 1], [0, 1]]

    class Config:
        env_file = ".env"
