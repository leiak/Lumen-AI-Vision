from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api import areas, cameras, edge, events, health, reviews
from app.api import auth, models, notifications, tasks, users
from app.api import audit, metrics
from app.api import training_samples
from app.api import keyframes
from app.core.security import hash_password
from app.models import User
from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(cameras.router)
app.include_router(areas.router)
app.include_router(edge.router)
app.include_router(events.router)
app.include_router(reviews.router)
app.include_router(models.router)
app.include_router(tasks.router)
app.include_router(notifications.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(training_samples.router)
app.include_router(keyframes.router)
app.mount("/metrics", make_asgi_app())


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        settings = get_settings()
        if not db.query(User).filter(User.username == settings.default_admin_username).first():
            db.add(
                User(
                    id="00000000-0000-0000-0000-000000000001",
                    username=settings.default_admin_username,
                    hashed_password=hash_password(settings.default_admin_password),
                    full_name="System Admin",
                    role=settings.default_admin_role,
                )
            )
            db.commit()
    finally:
        db.close()
