"""跨摄像头去重（AreaGroup + 三级 dedup_key）测试。"""

from datetime import datetime

import pytest

from app.models import Area, AreaGroup, Camera, Event, VehicleTrack, area_group_members
from app.services.dedup import DedupContext, build_dedup_key, find_duplicate, find_area_group_id


@pytest.fixture
def fresh_db(db_session):
    """清理本测试关心的表，确保用例之间相互隔离。"""
    db_session.execute(area_group_members.delete())
    db_session.query(Event).delete()
    db_session.query(VehicleTrack).delete()
    db_session.query(Area).delete()
    db_session.query(AreaGroup).delete()
    db_session.query(Camera).delete()
    db_session.commit()
    return db_session


def _camera(db, cam_id, name=None) -> Camera:
    camera = Camera(id=cam_id, name=name or cam_id, status="online")
    db.add(camera)
    db.flush()
    return camera


def _area(db, area_id, camera_id) -> Area:
    area = Area(id=area_id, camera_id=camera_id, name="gate", stay_threshold_seconds=300, high_risk_seconds=600)
    db.add(area)
    db.flush()
    return area


def test_dedup_lvl1_with_plate_and_area_group(fresh_db):
    _camera(fresh_db, "cam-1")
    area_a = _area(fresh_db, "area-1", "cam-1")
    area_b = _area(fresh_db, "area-2", "cam-1")
    group = AreaGroup(id="grp-1", name="主库门", priority=10, dedup_window_seconds=600)
    group.areas = [area_a, area_b]
    fresh_db.add(group)
    fresh_db.commit()

    key_a = build_dedup_key(
        fresh_db,
        DedupContext(
            camera_id="cam-1",
            area_id="area-1",
            track_id="track-A",
            plate_hash="plate-hash-X",
            vehicle_type="truck",
            start_time=datetime(2026, 9, 25, 10, 0, 0),
        ),
    )
    key_b = build_dedup_key(
        fresh_db,
        DedupContext(
            camera_id="cam-1",
            area_id="area-2",
            track_id="track-B",
            plate_hash="plate-hash-X",
            vehicle_type="truck",
            start_time=datetime(2026, 9, 25, 10, 1, 0),
        ),
    )
    assert key_a == key_b
    assert key_a.startswith("lvl1:")


def test_dedup_lvl3_when_no_plate(fresh_db):
    _camera(fresh_db, "cam-1")
    area = _area(fresh_db, "area-1", "cam-1")
    group = AreaGroup(id="grp-2", name="主库门", priority=0, dedup_window_seconds=600)
    group.areas = [area]
    fresh_db.add(group)
    fresh_db.commit()

    key = build_dedup_key(
        fresh_db,
        DedupContext(
            camera_id="cam-1",
            area_id="area-1",
            track_id="track-A",
            plate_hash=None,
            vehicle_type="truck",
            start_time=datetime(2026, 9, 25, 10, 0, 0),
        ),
    )
    assert key.startswith("lvl3:")
    later_key = build_dedup_key(
        fresh_db,
        DedupContext(
            camera_id="cam-1",
            area_id="area-1",
            track_id="track-A",
            plate_hash=None,
            vehicle_type="truck",
            start_time=datetime(2026, 9, 25, 10, 20, 0),
        ),
    )
    assert later_key != key


def test_find_area_group_returns_highest_priority(fresh_db):
    _camera(fresh_db, "cam-1")
    area = _area(fresh_db, "area-1", "cam-1")
    g1 = AreaGroup(id="grp-low", name="low", priority=1, dedup_window_seconds=600)
    g1.areas = [area]
    g2 = AreaGroup(id="grp-high", name="high", priority=5, dedup_window_seconds=600)
    g2.areas = [area]
    fresh_db.add_all([g1, g2])
    fresh_db.commit()

    assert find_area_group_id(fresh_db, "area-1") == "grp-high"


def test_find_duplicate_picks_earliest_in_window(fresh_db):
    _camera(fresh_db, "cam-1")
    _area(fresh_db, "area-1", "cam-1")
    fresh_db.add(VehicleTrack(id="t-1", camera_id="cam-1", area_id="area-1", start_time=datetime(2026, 9, 25, 10, 0, 0)))
    e1 = Event(id="evt-1", camera_id="cam-1", area_id="area-1", track_id="t-1",
               event_type="abnormal_stay", risk_level="medium", start_time=datetime(2026, 9, 25, 10, 0, 0),
               dedup_key="lvl3:t-1:area-1:bucket")
    e2 = Event(id="evt-2", camera_id="cam-1", area_id="area-1", track_id="t-1",
               event_type="abnormal_stay", risk_level="high", start_time=datetime(2026, 9, 25, 10, 1, 0),
               dedup_key="lvl3:t-1:area-1:bucket")
    fresh_db.add_all([e1, e2])
    fresh_db.commit()

    found = find_duplicate(fresh_db, "lvl3:t-1:area-1:bucket", datetime(2026, 9, 25, 10, 0, 30), window_seconds=600)
    assert found is not None
    assert found.id == "evt-1"