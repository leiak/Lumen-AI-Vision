import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Event, Review
from app.models import TrainingSample
from app.schemas import ReviewCreate, ReviewRead

router = APIRouter(prefix="/api/v1/events", tags=["reviews"])


@router.post("/{event_id}/review", response_model=ReviewRead)
def review_event(event_id: str, payload: ReviewCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Review:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    review = Review(**payload.model_dump(), id=str(uuid.uuid4()), event_id=event_id)
    if payload.corrected_event_type:
        event.event_type = payload.corrected_event_type
    if payload.corrected_risk_level:
        event.risk_level = payload.corrected_risk_level
    event.status = "confirmed" if payload.result == "abnormal" else "rejected"
    if payload.result in {"abnormal", "normal"}:
        db.add(
            TrainingSample(
                id=str(uuid.uuid4()),
                event_id=event.id,
                review_id=review.id,
                label=payload.result,
                risk_level=event.risk_level,
                reviewer_id=payload.reviewer_id,
            )
        )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
