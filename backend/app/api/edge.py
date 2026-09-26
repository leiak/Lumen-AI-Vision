from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_edge_key
from app.core.metrics import EDGE_EVENTS, EDGE_KEYFRAMES, EDGE_UPLOAD_FAILURES
from app.models import Area, Camera, Event, Keyframe, PersonBehaviorResult, PersonTrack, VehicleTrack
from app.schemas import EventCreate, KeyframeCreate
from app.services.event_service import create_task_for_event, event_risk_level
from app.services.dedup import DedupContext, build_dedup_key, find_duplicate
from app.services.storage import object_name, upload_bytes

router = APIRouter(prefix="/api/v1/edge", tags=["edge"], dependencies=[Depends(verify_edge_key)])


@router.post("/events")
def report_event(payload: EventCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Camera, payload.camera_id):
        raise HTTPException(status_code=404, detail="camera not found")
    area = db.get(Area, payload.area_id)
    if not area:
        raise HTTPException(status_code=404, detail="area not found")
    if not db.get(VehicleTrack, payload.track.id):
        track = VehicleTrack(
            id=payload.track.id,
            camera_id=payload.track.camera_id,
            area_id=payload.track.area_id,
            vehicle_type=payload.track.vehicle_type,
            start_time=payload.track.start_time,
            enter_area_time=payload.track.start_time,
            static_seconds=payload.track.static_seconds,
            status=payload.track.status,
        )
        db.add(track)
        db.flush()
    for behavior in payload.behaviors:
        behavior.vehicle_track_id = behavior.vehicle_track_id or payload.track.id
        person = db.get(PersonTrack, behavior.person_track_id)
        if person:
            person.last_seen_at = max(person.last_seen_at, behavior.sequence_end_time)
            person.confidence = max(person.confidence, behavior.behavior_confidence)
        else:
            person = PersonTrack(
                id=behavior.person_track_id,
                vehicle_track_id=payload.track.id,
                camera_id=payload.camera_id,
                area_id=payload.area_id,
                first_seen_at=behavior.sequence_start_time,
                last_seen_at=behavior.sequence_end_time,
                confidence=behavior.behavior_confidence,
            )
            db.add(person)

    risk_level = event_risk_level(area, payload.duration_seconds, payload.behaviors)

    event_id = f"evt-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    if payload.dedup_key:
        # 边缘端提供了显式 dedup_key（一般是 track 维度），仅作为兜底
        dedup_key = payload.dedup_key
    else:
        dedup_key = build_dedup_key(
            db,
            DedupContext(
                camera_id=payload.camera_id,
                area_id=payload.area_id,
                track_id=payload.track.id,
                plate_hash=payload.vehicle_plate_hash,
                vehicle_type=payload.track.vehicle_type or "unknown",
                start_time=payload.start_time,
            ),
        )
    existing = find_duplicate(db, dedup_key, payload.start_time, window_seconds=600)
    if existing:
        db.commit()
        return {
            "event_id": existing.id,
            "task_id": None,
            "risk_level": existing.risk_level,
            "accepted_keyframes": [],
            "deduplicated": True,
        }
    event = Event(
        id=event_id,
        camera_id=payload.camera_id,
        area_id=payload.area_id,
        track_id=payload.track.id,
        event_type=payload.event_type_hint,
        risk_level=risk_level,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_seconds=payload.duration_seconds,
        status="candidate",
        vehicle_plate_hash=payload.vehicle_plate_hash,
        dedup_key=dedup_key,
    )
    db.add(event)
    for behavior in payload.behaviors:
        db.add(
            PersonBehaviorResult(
                id=str(uuid.uuid4()),
                event_id=event_id,
                person_track_id=behavior.person_track_id,
                vehicle_track_id=behavior.vehicle_track_id or payload.track.id,
                behavior_label=behavior.behavior_label,
                behavior_confidence=behavior.behavior_confidence,
                near_vehicle_seconds=behavior.near_vehicle_seconds,
                sequence_frame_count=behavior.sequence_frame_count,
                sequence_start_time=behavior.sequence_start_time,
                sequence_end_time=behavior.sequence_end_time,
                model_type=behavior.model_type,
                model_version=behavior.model_version,
                output=behavior.output or {},
            )
        )
    frame_ids = []
    for frame in payload.keyframes:
        if db.get(Keyframe, frame.id):
            continue
        keyframe = Keyframe(**frame.model_dump(), track_id=payload.track.id, event_id=event_id)
        db.add(keyframe)
        frame_ids.append(frame.id)
    db.flush()
    task_id = None
    if event.risk_level in {"medium", "high", "critical"}:
        task = create_task_for_event(db, event)
        task_id = task.id
    db.commit()
    EDGE_EVENTS.labels(
        camera_id=payload.camera_id, area_id=payload.area_id, risk_level=event.risk_level
    ).inc()
    for frame in frame_ids:
        EDGE_KEYFRAMES.labels(frame_role="event_payload").inc()
    return {"event_id": event_id, "task_id": task_id, "risk_level": event.risk_level, "accepted_keyframes": frame_ids}


@router.post("/keyframes")
def report_keyframe(payload: KeyframeCreate, track_id: str, event_id: str | None = None, db: Session = Depends(get_db)) -> dict[str, str]:
    if not db.get(VehicleTrack, track_id):
        raise HTTPException(status_code=404, detail="track not found")
    if db.get(Keyframe, payload.id):
        return {"id": payload.id}
    keyframe = Keyframe(**payload.model_dump(), track_id=track_id, event_id=event_id)
    db.add(keyframe)
    db.commit()
    EDGE_KEYFRAMES.labels(frame_role=payload.frame_role).inc()
    return {"id": payload.id}


@router.post("/keyframes/upload")
def upload_keyframe(
    track_id: str = Form(...),
    event_id: str | None = Form(None),
    frame_id: str | None = Form(None),
    frame_role: str = Form("state_change"),
    timestamp: datetime = Form(...),
    privacy_processed: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    track = db.get(VehicleTrack, track_id)
    if not track:
        EDGE_UPLOAD_FAILURES.labels(reason="track_not_found").inc()
        raise HTTPException(status_code=404, detail="track not found")
    if event_id and not db.get(Event, event_id):
        EDGE_UPLOAD_FAILURES.labels(reason="event_not_found").inc()
        raise HTTPException(status_code=404, detail="event not found")
    data = file.file.read()
    if not data:
        EDGE_UPLOAD_FAILURES.labels(reason="empty_file").inc()
        raise HTTPException(status_code=400, detail="empty file")
    object_key = object_name(f"keyframes/{track_id}")
    storage_url = upload_bytes(object_key, data, file.content_type)
    if frame_id and db.get(Keyframe, frame_id):
        keyframe = db.get(Keyframe, frame_id)
        keyframe.storage_url = storage_url
        keyframe.event_id = event_id
        keyframe.frame_role = frame_role
        keyframe.privacy_processed = privacy_processed
        db.commit()
        return {"id": keyframe.id, "storage_url": storage_url}
    keyframe = Keyframe(
        id=frame_id or f"frame-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        track_id=track_id,
        event_id=event_id,
        timestamp=timestamp,
        storage_url=storage_url,
        frame_role=frame_role,
        privacy_processed=privacy_processed,
    )
    db.add(keyframe)
    db.commit()
    EDGE_KEYFRAMES.labels(frame_role=frame_role).inc()
    return {"id": keyframe.id, "storage_url": storage_url}


@router.get("/config")
def fetch_edge_config(
    camera_id: str,
    area_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """边缘端拉取最新的运行参数（阈值、节奏），用于热更新。

    返回 revision 字段，客户端在相同 revision 时应跳过应用。
    """
    if not db.get(Camera, camera_id):
        raise HTTPException(status_code=404, detail="camera not found")
    area = db.get(Area, area_id) if area_id else None
    revision = int(datetime.utcnow().timestamp())
    payload: dict = {
        "revision": revision,
        "camera_id": camera_id,
        "area_id": area_id,
        "stay_threshold_seconds": area.stay_threshold_seconds if area else 300,
        "high_risk_seconds": area.high_risk_seconds if area else 600,
        "keyframe_interval_seconds": 10,
        "movement_threshold_pixels": 15.0,
        "lost_track_tolerance_seconds": 2.0,
        "pose_sample_fps": 2.0,
        "person_loitering_seconds": 120.0,
        "person_movement_threshold_pixels": 12.0,
        "person_lost_tolerance_seconds": 1.0,
        "person_near_vehicle_margin_pixels": 120.0,
    }
    return payload
