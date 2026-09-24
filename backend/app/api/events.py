from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Event, Keyframe
from app.models import ModelResult
from app.schemas import EventRead, ModelResultRead

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", response_model=list[EventRead])
def list_events(
    camera_id: str | None = None,
    area_id: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[Event]:
    query = db.query(Event)
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if area_id:
        query = query.filter(Event.area_id == area_id)
    if risk_level:
        query = query.filter(Event.risk_level == risk_level)
    if status:
        query = query.filter(Event.status == status)
    return query.order_by(Event.start_time.desc()).all()


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    return event


@router.get("/{event_id}/keyframes")
def get_event_keyframes(event_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[dict]:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    return [
        {
            "id": item.id,
            "timestamp": item.timestamp,
            "storage_url": item.storage_url,
            "frame_role": item.frame_role,
        }
        for item in db.query(Keyframe).filter(Keyframe.event_id == event_id).all()
    ]

@router.get("/{event_id}/model-results", response_model=list[ModelResultRead])
def get_event_model_results(event_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[ModelResult]:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    return db.query(ModelResult).filter(ModelResult.event_id == event_id).all()
