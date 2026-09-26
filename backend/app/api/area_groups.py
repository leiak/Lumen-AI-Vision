from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.models import Area, AreaGroup, User
from app.schemas import AreaGroupCreate, AreaGroupRead, AreaGroupUpdate

router = APIRouter(prefix="/api/v1/area-groups", tags=["area-groups"])


def _serialize(group: AreaGroup) -> AreaGroupRead:
    return AreaGroupRead(
        id=group.id,
        name=group.name,
        area_ids=[area.id for area in group.areas],
        priority=group.priority,
        dedup_window_seconds=group.dedup_window_seconds,
    )


@router.post("", response_model=AreaGroupRead)
def create_area_group(
    payload: AreaGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
) -> AreaGroupRead:
    if db.get(AreaGroup, payload.id):
        raise HTTPException(status_code=409, detail="area_group already exists")
    areas = db.query(Area).filter(Area.id.in_(payload.area_ids or [])).all()
    if len(areas) != len(set(payload.area_ids or [])):
        raise HTTPException(status_code=404, detail="one or more areas not found")
    group = AreaGroup(
        id=payload.id,
        name=payload.name,
        priority=payload.priority,
        dedup_window_seconds=payload.dedup_window_seconds,
        areas=areas,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _serialize(group)


@router.get("", response_model=list[AreaGroupRead])
def list_area_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AreaGroupRead]:
    return [_serialize(item) for item in db.query(AreaGroup).order_by(AreaGroup.priority.desc()).all()]


@router.patch("/{group_id}", response_model=AreaGroupRead)
def update_area_group(
    group_id: str,
    payload: AreaGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
) -> AreaGroupRead:
    group = db.get(AreaGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="area_group not found")
    data = payload.model_dump(exclude_unset=True)
    if "area_ids" in data:
        areas = db.query(Area).filter(Area.id.in_(data["area_ids"])).all()
        if len(areas) != len(set(data["area_ids"])):
            raise HTTPException(status_code=404, detail="one or more areas not found")
        group.areas = areas
        data.pop("area_ids")
    for field, value in data.items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return _serialize(group)


@router.delete("/{group_id}")
def delete_area_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
) -> dict:
    group = db.get(AreaGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="area_group not found")
    db.delete(group)
    db.commit()
    return {"deleted": group_id}