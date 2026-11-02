from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.enums import MovementType, check_in
from app.models.hospital import Department


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("min_threshold >= 0 AND critical_threshold >= 0", name="thresholds_non_negative"),
        CheckConstraint("critical_threshold <= min_threshold", name="critical_below_min"),
        UniqueConstraint("name", "storage_location", name="uq_resources_name_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(60), default="General", index=True)
    unit: Mapped[str] = mapped_column(String(20), default="units")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    min_threshold: Mapped[int] = mapped_column(Integer, default=0)      # at/below -> "low"
    critical_threshold: Mapped[int] = mapped_column(Integer, default=0)  # at/below -> "critical"
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    storage_location: Mapped[str] = mapped_column(String(100), default="Main Store")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    department: Mapped[Department | None] = relationship(lazy="joined")


class ResourceMovement(Base):
    __tablename__ = "resource_movements"
    __table_args__ = (
        check_in("movement_type", MovementType, "type_valid"),
        CheckConstraint("quantity_after >= 0", name="after_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(20))
    quantity_change: Mapped[int] = mapped_column(Integer)  # signed
    quantity_before: Mapped[int] = mapped_column(Integer)
    quantity_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
