from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models import Area, Camera
from app.schemas import AreaCreate, AreaRead

router = APIRouter(prefix="/api/v1/areas", tags=["areas"])


@router.post("", response_model=AreaRead)
def create_area(payload: AreaCreate, db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "operator"))) -> Area:
    if not db.get(Camera, payload.camera_id):
        raise HTTPException(status_code=404, detail="camera not found")
    if db.get(Area, payload.id):
        raise HTTPException(status_code=409, detail="area already exists")
    area = Area(**payload.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@router.get("", response_model=list[AreaRead])
def list_areas(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[Area]:
    return db.query(Area).all()
