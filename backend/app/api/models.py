import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.models import Area, Event, Keyframe, ModelResult, User
from app.schemas import ModelResultRead, TemporalClassifyRequest, VLExplainRequest
from app.services.event_service import write_audit
from app.services.vl_service import explain_event

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.post("/temporal/classify", response_model=ModelResultRead)
def temporal_classify(
    payload: TemporalClassifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModelResult:
    settings = get_settings()
    event = db.get(Event, payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    area = db.get(Area, event.area_id)
    started = time.perf_counter()
    if not area or event.duration_seconds >= area.high_risk_seconds:
        label = "abnormal_stay"
        score = 0.92
    elif event.duration_seconds >= area.stay_threshold_seconds:
        label = "abnormal_stay"
        score = 0.78
    else:
        label = "normal_stay"
        score = 0.84
    latency_ms = int((time.perf_counter() - started) * 1000)
    result = ModelResult(
        id=str(uuid.uuid4()),
        event_id=event.id,
        model_name=settings.temporal_model_name,
        model_version=settings.temporal_model_version,
        model_type="temporal",
        label=label,
        score=score,
        output={"duration_seconds": event.duration_seconds, "decision": label},
        latency_ms=latency_ms,
    )
    event.risk_level = "high" if label == "abnormal_stay" and event.duration_seconds >= (area.high_risk_seconds if area else 600) else "medium" if label == "abnormal_stay" else "low"
    event.status = "confirmed" if label == "abnormal_stay" else "rejected"
    db.add(result)
    db.commit()
    write_audit(
        db,
        current_user.id,
        "temporal_classify",
        "event",
        event.id,
        before_value=None,
        after_value={"label": label, "score": score, "model_version": settings.temporal_model_version},
    )
    db.commit()
    db.refresh(result)
    return result


@router.post("/vl/explain", response_model=ModelResultRead)
def vl_explain(
    payload: VLExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModelResult:
    settings = get_settings()
    event = db.get(Event, payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    started = time.perf_counter()
    keyframes = db.query(Keyframe).filter(Keyframe.event_id == event.id).all()
    summary, output, score = explain_event(event, keyframes)
    latency_ms = int((time.perf_counter() - started) * 1000)
    result = ModelResult(
        id=str(uuid.uuid4()),
        event_id=event.id,
        model_name=settings.vl_model_name,
        model_version=settings.vl_model_version,
        model_type="vl",
        label="event_explanation",
        score=score,
        output=output,
        latency_ms=latency_ms,
    )
    event.summary = summary
    db.add(result)
    db.commit()
    write_audit(
        db,
        current_user.id,
        "vl_explain",
        "event",
        event.id,
        before_value=None,
        after_value={"model_version": settings.vl_model_version, "summary": summary[:200]},
    )
    db.commit()
    db.refresh(result)
    return result


@router.get("/accuracy")
def model_accuracy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """模型准确率统计（运维设计 §3.6）。

    返回每种模型类型的 precision / recall / f1 与混淆矩阵元素。
    """
    from app.services.model_evaluation import compute_accuracy

    reports = compute_accuracy(db)
    return [
        {
            "model_type": report.model_type,
            "sample_count": report.sample_count,
            "precision": round(report.precision, 4),
            "recall": round(report.recall, 4),
            "f1": round(report.f1, 4),
            "true_positive": report.true_positive,
            "false_positive": report.false_positive,
            "false_negative": report.false_negative,
            "true_negative": report.true_negative,
        }
        for report in reports
    ]
