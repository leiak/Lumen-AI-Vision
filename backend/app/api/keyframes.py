from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Keyframe, User
from app.services.storage import read_bytes

router = APIRouter(prefix="/api/v1/keyframes", tags=["keyframes"])


@router.get("/{frame_id}/file")
def read_keyframe_file(
    frame_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    keyframe = db.get(Keyframe, frame_id)
    if not keyframe:
        raise HTTPException(status_code=404, detail="keyframe not found")
    try:
        data, content_type = read_bytes(keyframe.storage_url)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="keyframe file not found")
    return Response(content=data, media_type=content_type)
