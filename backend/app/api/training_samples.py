from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import TrainingSample, User
from app.schemas import TrainingSampleRead

router = APIRouter(prefix="/api/v1/training-samples", tags=["training-samples"])


@router.get("", response_model=list[TrainingSampleRead])
def list_training_samples(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TrainingSample]:
    return db.query(TrainingSample).order_by(TrainingSample.created_at.desc()).all()
