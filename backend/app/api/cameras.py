from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models import Camera
from app.schemas import CameraCreate, CameraUpdate

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


@router.post("")
def create_camera(payload: CameraCreate, db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "operator"))) -> dict[str, str]:
    if db.get(Camera, payload.id):
        raise HTTPException(status_code=409, detail="camera already exists")
    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    return {"id": camera.id}


@router.get("")
def list_cameras(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[dict[str, str]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "location": item.location,
            "status": item.status,
        }
        for item in db.query(Camera).all()
    ]


@router.patch("/{camera_id}")
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "operator")),
) -> dict[str, str]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="camera not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera, field, value)
    db.commit()
    return {"id": camera.id}
