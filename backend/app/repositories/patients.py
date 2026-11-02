from sqlalchemy import Select, asc, desc, or_, select
from sqlalchemy.orm import Session

from app.models.hospital import Bed, BedAssignment, Patient

SORTABLE = {
    "patient_code": Patient.patient_code, "last_name": Patient.last_name, "status": Patient.status,
    "admitted_at": Patient.admitted_at, "created_at": Patient.created_at, "date_of_birth": Patient.date_of_birth,
}


def search_stmt(q: str | None, status: str | None, department_id: int | None, sort: str, order: str) -> Select:
    stmt = select(Patient)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Patient.patient_code.ilike(like), Patient.first_name.ilike(like), Patient.last_name.ilike(like)))
    if status:
        stmt = stmt.where(Patient.status == status)
    if department_id:
        stmt = stmt.where(Patient.department_id == department_id)
    col = SORTABLE.get(sort, Patient.created_at)
    return stmt.order_by(desc(col) if order == "desc" else asc(col), Patient.id)


def current_beds(db: Session, patient_ids: list[int]) -> dict[int, Bed]:
    if not patient_ids:
        return {}
    rows = db.execute(
        select(BedAssignment.patient_id, Bed).join(Bed, Bed.id == BedAssignment.bed_id)
        .where(BedAssignment.patient_id.in_(patient_ids), BedAssignment.released_at.is_(None))
    ).all()
    return {pid: bed for pid, bed in rows}
