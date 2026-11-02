from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.hospital import Bed, BedAssignment, Patient


def list_stmt(department_id: int | None, status: str | None, ward: str | None, q: str | None) -> Select:
    stmt = select(Bed)
    if department_id:
        stmt = stmt.where(Bed.department_id == department_id)
    if status:
        stmt = stmt.where(Bed.status == status)
    if ward:
        stmt = stmt.where(Bed.ward == ward)
    if q:
        stmt = stmt.where(Bed.code.ilike(f"%{q.strip()}%"))
    return stmt.order_by(Bed.department_id, Bed.ward, Bed.code)


def active_patients(db: Session, bed_ids: list[int]) -> dict[int, Patient]:
    if not bed_ids:
        return {}
    rows = db.execute(
        select(BedAssignment.bed_id, Patient).join(Patient, Patient.id == BedAssignment.patient_id)
        .where(BedAssignment.bed_id.in_(bed_ids), BedAssignment.released_at.is_(None))
    ).all()
    return {bid: p for bid, p in rows}


def assignment_history_stmt(bed_id: int | None, patient_id: int | None) -> Select:
    stmt = select(BedAssignment)
    if bed_id:
        stmt = stmt.where(BedAssignment.bed_id == bed_id)
    if patient_id:
        stmt = stmt.where(BedAssignment.patient_id == patient_id)
    return stmt.order_by(BedAssignment.assigned_at.desc(), BedAssignment.id.desc())
