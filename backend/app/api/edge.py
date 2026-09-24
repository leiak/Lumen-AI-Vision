from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_edge_key
from app.core.metrics import EDGE_EVENTS, EDGE_KEYFRAMES, EDGE_UPLOAD_FAILURES
from app.models import Area, Camera, Event, Keyframe, VehicleTrack
from app.schemas import EventCreate, KeyframeCreate
from app.services.event_service import create_task_for_event
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
    if payload.duration_seconds >= area.high_risk_seconds:
        risk_level = "high"
    elif payload.duration_seconds >= area.stay_threshold_seconds:
        risk_level = "medium"
    else:
        risk_level = "low"

    event_id = f"evt-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    dedup_key = payload.dedup_key or f"{payload.camera_id}:{payload.area_id}:{payload.track.id}:{payload.start_time.isoformat()}"
    existing = db.query(Event).filter(Event.dedup_key == dedup_key).first()
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
        keyframe.privacy_processed = False
        db.commit()
        return {"id": keyframe.id, "storage_url": storage_url}
    keyframe = Keyframe(
        id=frame_id or f"frame-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        track_id=track_id,
        event_id=event_id,
        timestamp=timestamp,
        storage_url=storage_url,
        frame_role=frame_role,
        privacy_processed=False,
    )
    db.add(keyframe)
    db.commit()
    EDGE_KEYFRAMES.labels(frame_role=frame_role).inc()
    return {"id": keyframe.id, "storage_url": storage_url}
