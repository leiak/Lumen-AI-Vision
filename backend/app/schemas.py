from datetime import datetime

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    id: str
    name: str
    location: str | None = None
    stream_url: str | None = None
    edge_node_id: str | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    status: str | None = None
    stream_url: str | None = None
    edge_node_id: str | None = None


class AreaCreate(BaseModel):
    id: str
    camera_id: str
    name: str
    area_type: str = "gate"
    polygon: list[list[float]] = []
    stay_threshold_seconds: int = 300
    high_risk_seconds: int = 600


class AreaUpdate(BaseModel):
    name: str | None = None
    area_type: str | None = None
    polygon: list[list[float]] | None = None
    stay_threshold_seconds: int | None = None
    high_risk_seconds: int | None = None
    enabled: bool | None = None


class AreaRead(AreaCreate):
    enabled: bool = True


class AreaGroupCreate(BaseModel):
    id: str
    name: str
    area_ids: list[str] = []
    priority: int = 0
    dedup_window_seconds: int = 600


class AreaGroupUpdate(BaseModel):
    name: str | None = None
    area_ids: list[str] | None = None
    priority: int | None = None
    dedup_window_seconds: int | None = None


class AreaGroupRead(BaseModel):
    id: str
    name: str
    area_ids: list[str]
    priority: int
    dedup_window_seconds: int

    class Config:
        from_attributes = True


class KeyframeCreate(BaseModel):
    id: str
    timestamp: datetime
    storage_url: str
    frame_role: str = "state_change"
    width: int | None = None
    height: int | None = None
    quality_score: float | None = None
    detected_objects: list[dict] = []
    privacy_processed: bool = True


class TrackCreate(BaseModel):
    id: str
    camera_id: str
    area_id: str
    vehicle_type: str = "unknown"
    start_time: datetime
    status: str = "static"
    static_seconds: int = 0


class PersonBehaviorCreate(BaseModel):
    person_track_id: str
    vehicle_track_id: str | None = None
    behavior_label: str
    behavior_confidence: float = Field(default=0.0, ge=0, le=1)
    near_vehicle_seconds: float = Field(default=0.0, ge=0)
    sequence_frame_count: int = Field(default=0, ge=0)
    sequence_start_time: datetime
    sequence_end_time: datetime
    model_type: str = "rule"
    model_version: str = "person-behavior-rule-v1"
    output: dict | list | None = None


class PersonBehaviorRead(PersonBehaviorCreate):
    id: str
    event_id: str

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    camera_id: str
    area_id: str
    track: TrackCreate
    event_type_hint: str = "abnormal_stay"
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: int = 0
    keyframes: list[KeyframeCreate] = []
    behaviors: list[PersonBehaviorCreate] = []
    vehicle_plate_hash: str | None = None
    dedup_key: str | None = None


class EventRead(BaseModel):
    id: str
    camera_id: str
    area_id: str
    track_id: str
    event_type: str
    risk_level: str
    start_time: datetime
    end_time: datetime | None
    duration_seconds: int
    status: str
    summary: str | None
    vehicle_plate_hash: str | None = None
    dedup_key: str | None = None
    behavior_results: list[PersonBehaviorRead] = []

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    reviewer_id: str
    result: str
    corrected_event_type: str | None = None
    corrected_risk_level: str | None = None
    comment: str | None = None


class ReviewRead(ReviewCreate):
    id: str
    event_id: str
    reviewed_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "viewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    password: str | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    id: str
    username: str
    full_name: str | None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TaskCreate(BaseModel):
    event_id: str
    assignee_id: str
    assignee_role: str = "security"
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    status: str | None = None
    result: str | None = None
    comment: str | None = None
    due_at: datetime | None = None


class TaskRead(BaseModel):
    id: str
    event_id: str
    assignee_id: str
    assignee_role: str
    status: str
    due_at: datetime | None
    result: str | None
    comment: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationRead(BaseModel):
    id: str
    event_id: str
    task_id: str | None
    receiver_id: str
    receiver_role: str
    channel: str
    status: str
    retry_count: int
    sent_at: datetime | None
    read_at: datetime | None

    class Config:
        from_attributes = True


class ModelResultRead(BaseModel):
    id: str
    event_id: str
    model_name: str
    model_version: str
    model_type: str
    label: str
    score: float
    output: dict | list | None
    latency_ms: int

    class Config:
        from_attributes = True


class TemporalClassifyRequest(BaseModel):
    event_id: str


class VLExplainRequest(BaseModel):
    event_id: str


class TrainingSampleRead(BaseModel):
    id: str
    event_id: str
    review_id: str
    label: str
    risk_level: str
    reviewer_id: str
    used_for_training: bool

    class Config:
        from_attributes = True
