from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.enums import BedStatus, DepartmentStatus, PatientStatus, check_in


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        check_in("status", DepartmentStatus, "status_valid"),
        CheckConstraint("capacity >= 0", name="capacity_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=0)  # max concurrent patients (0 = bed-limited only)
    status: Mapped[str] = mapped_column(String(20), default=DepartmentStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Patient(Base):
    """Synthetic demo patients only. Operational record, not a clinical record."""

    __tablename__ = "patients"
    __table_args__ = (check_in("status", PatientStatus, "status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # internal identifier, e.g. PT-000012
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=PatientStatus.REGISTERED.value, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    requested_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    admitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    discharged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    department: Mapped[Department | None] = relationship(foreign_keys=[department_id], lazy="joined")


class Bed(Base):
    __tablename__ = "beds"
    __table_args__ = (check_in("status", BedStatus, "status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    ward: Mapped[str] = mapped_column(String(60), default="General")
    status: Mapped[str] = mapped_column(String(20), default=BedStatus.AVAILABLE.value, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    department: Mapped[Department] = relationship(lazy="joined")


class BedAssignment(Base):
    """History table. At most ONE active (released_at IS NULL) row per bed and per patient (partial unique indexes)."""

    __tablename__ = "bed_assignments"
    __table_args__ = (
        Index("uq_bed_assignments_active_bed", "bed_id", unique=True,
              sqlite_where=text("released_at IS NULL"), postgresql_where=text("released_at IS NULL")),
        Index("uq_bed_assignments_active_patient", "patient_id", unique=True,
              sqlite_where=text("released_at IS NULL"), postgresql_where=text("released_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)  # discharge|transfer|reassignment|manual
