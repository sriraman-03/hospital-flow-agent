from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.enums import DischargeStatus, TransferStatus, check_in


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        check_in("status", TransferStatus, "status_valid"),
        # one open transfer per patient
        Index("uq_transfers_open_patient", "patient_id", unique=True,
              sqlite_where=text("status IN ('requested','approved','in_progress')"),
              postgresql_where=text("status IN ('requested','approved','in_progress')")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    source_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    destination_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    destination_bed_id: Mapped[int | None] = mapped_column(ForeignKey("beds.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TransferStatus.REQUESTED.value, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Discharge(Base):
    __tablename__ = "discharges"
    __table_args__ = (
        check_in("status", DischargeStatus, "status_valid"),
        Index("uq_discharges_open_patient", "patient_id", unique=True,
              sqlite_where=text("status IN ('requested','approved')"),
              postgresql_where=text("status IN ('requested','approved')")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DischargeStatus.REQUESTED.value, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # operational notes only
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
