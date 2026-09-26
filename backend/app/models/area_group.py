from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# 区域组成员关系表（多对多）
area_group_members = Table(
    "area_group_members",
    Base.metadata,
    Column("area_group_id", String(36), ForeignKey("area_groups.id"), primary_key=True),
    Column("area_id", String(36), ForeignKey("areas.id"), primary_key=True),
)


class AreaGroup(Base):
    """区域组：用于跨摄像头去重，把同一物理区域（如"主库门"）的多个 area 关联到一起。"""

    __tablename__ = "area_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    dedup_window_seconds: Mapped[int] = mapped_column(Integer, default=600)

    areas: Mapped[list["Area"]] = relationship(
        "Area",
        secondary=area_group_members,
        back_populates="area_groups",
    )