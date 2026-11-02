from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.enums import NotificationCategory, NotificationSeverity, check_in


class Notification(Base):
    """Notification state (read / acknowledged / resolved) is shared across staff and persisted here."""

    __tablename__ = "notifications"
    __table_args__ = (
        check_in("category", NotificationCategory, "category_valid"),
        check_in("severity", NotificationSeverity, "severity_valid"),
        # Only one UNRESOLVED notification per deduplication key (NULL keys are unconstrained).
        Index("uq_notifications_open_dedup", "dedup_key", unique=True,
              sqlite_where=text("is_resolved = 0"), postgresql_where=text("is_resolved = false")),
        Index("ix_notifications_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)  # idempotency
