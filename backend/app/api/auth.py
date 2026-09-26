import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import LoginRequest, UserRead
from app.services.event_service import write_audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        write_audit(
            db,
            user_id=user.id if user else "anonymous",
            action="login_failed",
            resource_type="user",
            resource_id=user.id if user else payload.username,
            after_value={"username": payload.username, "reason": "bad credentials"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user disabled")
    write_audit(
        db,
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        after_value={"username": user.username, "role": user.role},
    )
    db.commit()
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer"}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout")
def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    write_audit(
        db,
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=current_user.id,
    )
    db.commit()
    return {"status": "logged_out"}