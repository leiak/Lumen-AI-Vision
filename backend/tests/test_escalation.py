"""任务升级服务测试。"""

from datetime import datetime, timedelta

import pytest

from app.models import Event, Notification, Task, User, VehicleTrack
from app.services.escalation import escalate_overdue_tasks


@pytest.fixture
def escalation_db(db_session):
    """清理相关表后返回 session。"""
    db_session.query(Notification).delete()
    db_session.query(Task).delete()
    db_session.query(Event).delete()
    db_session.query(VehicleTrack).delete()
    db_session.query(User).delete()
    db_session.commit()
    assert db_session.query(User).count() == 0, "fixture failed to clean users"
    return db_session


def _user(db, role="supervisor", username=None) -> User:
    username = username or f"{role}-user"
    user = User(
        id=f"user-{role}-{username}",
        username=username,
        full_name=username,
        role=role,
        is_active=True,
        hashed_password="x",
    )
    db.add(user)
    db.flush()
    return user


def _event(db, risk_level="high") -> Event:
    db.add(VehicleTrack(id="track-1", camera_id="cam-1", area_id="area-1",
                        start_time=datetime(2026, 9, 25, 10, 0, 0)))
    event = Event(
        id="evt-1",
        camera_id="cam-1",
        area_id="area-1",
        track_id="track-1",
        event_type="abnormal_stay",
        risk_level=risk_level,
        start_time=datetime(2026, 9, 25, 10, 0, 0),
        duration_seconds=600,
    )
    db.add(event)
    db.flush()
    return event


def _task(db, due_at, escalation_level=0) -> Task:
    task = Task(
        id="task-1",
        event_id="evt-1",
        assignee_id="user-security-1",
        assignee_role="security",
        status="pending",
        due_at=due_at,
        escalation_level=escalation_level,
    )
    db.add(task)
    db.flush()
    return task


def test_high_risk_escalates_to_supervisor_once(escalation_db):
    _user(escalation_db, "supervisor")
    event = _event(escalation_db, "high")
    task = _task(escalation_db, datetime.utcnow() - timedelta(minutes=10))
    escalation_db.commit()

    upgraded = escalate_overdue_tasks(escalation_db)
    assert len(upgraded) == 1
    assert upgraded[0].status == "escalated"
    assert upgraded[0].escalation_level == 1

    notifications = escalation_db.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].receiver_role == "supervisor"
    assert notifications[0].escalation_level == 1

    # 任务已经被标记为 escalated，再次扫描不再处理
    upgraded_again = escalate_overdue_tasks(escalation_db)
    assert upgraded_again == []
    assert escalation_db.query(Notification).count() == 1


def test_critical_risk_first_escalates_to_duty_admin(escalation_db):
    _user(escalation_db, "duty_admin")
    event = _event(escalation_db, "critical")
    task = _task(escalation_db, datetime.utcnow() - timedelta(minutes=5))
    escalation_db.commit()

    upgraded = escalate_overdue_tasks(escalation_db)
    assert upgraded[0].escalation_level == 1
    notifications = escalation_db.query(Notification).all()
    assert {n.receiver_role for n in notifications} == {"duty_admin"}


def test_critical_risk_second_escalation_notifies_supervisor_and_ops(escalation_db):
    _user(escalation_db, "supervisor")
    _user(escalation_db, "ops_lead")
    _user(escalation_db, "duty_admin")
    _event(escalation_db, "critical")
    _task(escalation_db, datetime.utcnow() - timedelta(minutes=5), escalation_level=1)
    escalation_db.commit()

    upgraded = escalate_overdue_tasks(escalation_db)
    assert upgraded[0].escalation_level == 2
    roles = {n.receiver_role for n in escalation_db.query(Notification).all()}
    assert {"supervisor", "ops_lead"} <= roles


def test_non_overdue_tasks_are_untouched(escalation_db):
    _user(escalation_db, "supervisor")
    _event(escalation_db, "high")
    _task(escalation_db, datetime.utcnow() + timedelta(minutes=10))
    escalation_db.commit()

    upgraded = escalate_overdue_tasks(escalation_db)
    assert upgraded == []
    assert escalation_db.query(Notification).count() == 0


def test_escalation_falls_back_to_admin_when_role_missing(escalation_db):
    # 无 supervisor 用户 → 通知 admin 兜底
    # 先确保没有任何 supervisor 用户
    escalation_db.query(User).filter(User.role == "supervisor").delete()
    escalation_db.commit()
    _user(escalation_db, "admin", "admin-1")
    _event(escalation_db, "high")
    _task(escalation_db, datetime.utcnow() - timedelta(minutes=10))
    escalation_db.commit()

    escalate_overdue_tasks(escalation_db)
    notifications = escalation_db.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].receiver_role == "admin"