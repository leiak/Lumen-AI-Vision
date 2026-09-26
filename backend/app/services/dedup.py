"""跨摄像头事件去重。

去重优先级（与运维设计 §6.1 对齐）：
  L1 - plate_hash + area_group + 时间窗口
  L2 - vehicle_type + vehicle_color + direction + 时间窗口
  L3 - track_id + area_group + 时间窗口

L2 字段尚未在数据模型中，我们保留接口但默认降级到 L1/L3。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Area, AreaGroup, Event, VehicleTrack


@dataclass(frozen=True)
class DedupContext:
    camera_id: str
    area_id: str
    track_id: str
    plate_hash: str | None
    vehicle_type: str
    start_time: datetime


def find_area_group_id(db: Session, area_id: str) -> str | None:
    """返回 area_id 所属的最高优先级 AreaGroup id；无归属则返回 None。"""
    area = db.get(Area, area_id)
    if not area or not area.area_groups:
        return None
    groups = sorted(area.area_groups, key=lambda item: (item.priority, item.id), reverse=True)
    return groups[0].id


def build_dedup_key(db: Session, ctx: DedupContext, default_window_seconds: int = 600) -> str:
    """按 L1→L3 优先级返回首个可用的去重 key。

    返回的 key 形如 ``lvl1:<plate>:<area_group>:<bucket>``；若无法构造 L1 则降级到 L3。
    """
    area_group_id = find_area_group_id(db, ctx.area_id)
    window = default_window_seconds
    if area_group_id:
        group = db.get(AreaGroup, area_group_id)
        if group:
            window = group.dedup_window_seconds or window
    bucket = int(ctx.start_time.timestamp() // max(window, 1))

    # L1: plate_hash + area_group + time_bucket
    if ctx.plate_hash and area_group_id:
        return f"lvl1:{ctx.plate_hash}:{area_group_id}:{bucket}"

    # L3: track_id + area_group + time_bucket
    if area_group_id:
        return f"lvl3:{ctx.track_id}:{area_group_id}:{bucket}"

    # 无 area_group 时的最终兜底（与旧逻辑兼容）
    return f"lvl3:{ctx.camera_id}:{ctx.area_id}:{ctx.track_id}:{bucket}"


def find_duplicate(db: Session, dedup_key: str, start_time: datetime, window_seconds: int) -> Event | None:
    """在去重 key 命中的事件中，挑选窗口内最早的一个作为主事件。"""
    candidates = db.query(Event).filter(Event.dedup_key == dedup_key).all()
    earliest: Event | None = None
    for event in candidates:
        if abs((event.start_time - start_time).total_seconds()) <= window_seconds:
            if earliest is None or event.start_time < earliest.start_time:
                earliest = event
    return earliest


def attach_dedup_context_from_track(db: Session, track: VehicleTrack) -> DedupContext:
    """从已持久化的 track 推导 DedupContext，缺少 plate_hash 时退回到空字符串。"""
    return DedupContext(
        camera_id=track.camera_id,
        area_id=track.area_id,
        track_id=track.id,
        plate_hash=None,
        vehicle_type=track.vehicle_type or "unknown",
        start_time=track.start_time,
    )