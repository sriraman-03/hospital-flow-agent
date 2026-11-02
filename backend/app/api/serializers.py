"""Converts ORM objects into response schemas with bulk lookups (avoids N+1 queries)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.hospital import Bed, BedAssignment, Department, Patient
from app.models.inventory import Resource
from app.models.workflow import Discharge, Transfer
from app.repositories import beds as bed_repo
from app.repositories import patients as patient_repo
from app.schemas.hospital import AssignmentOut, BedOut, DepartmentOut, PatientOut
from app.schemas.operations import DischargeOut, ResourceOut, TransferOut
from app.services import capacity_service, resource_service, routing_service


def patients_out(db: Session, patients: list[Patient]) -> list[PatientOut]:
    beds = patient_repo.current_beds(db, [p.id for p in patients])
    out = []
    for p in patients:
        o = PatientOut.model_validate(p)
        o.department_name = p.department.name if p.department else None
        b = beds.get(p.id)
        o.bed_id, o.bed_code = (b.id, b.code) if b else (None, None)
        out.append(o)
    return out


def beds_out(db: Session, beds: list[Bed]) -> list[BedOut]:
    patients = bed_repo.active_patients(db, [b.id for b in beds])
    return [BedOut(id=b.id, code=b.code, department_id=b.department_id, department_name=b.department.name, ward=b.ward,
                   status=b.status, patient_id=patients[b.id].id if b.id in patients else None,
                   patient_code=patients[b.id].patient_code if b.id in patients else None) for b in beds]


def assignments_out(db: Session, rows: list[BedAssignment]) -> list[AssignmentOut]:
    beds = {b.id: b for b in db.scalars(select(Bed).where(Bed.id.in_({r.bed_id for r in rows})))} if rows else {}
    pats = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_({r.patient_id for r in rows})))} if rows else {}
    return [AssignmentOut(id=r.id, bed_id=r.bed_id, bed_code=beds[r.bed_id].code, patient_id=r.patient_id,
                          patient_code=pats[r.patient_id].patient_code, assigned_at=r.assigned_at,
                          released_at=r.released_at, release_reason=r.release_reason) for r in rows]


def department_out(db: Session, d: Department) -> DepartmentOut:
    s = capacity_service.department_bed_stats(db, d.id)
    low = db.scalar(select(func.count()).select_from(Resource).where(
        Resource.department_id == d.id, Resource.is_active.is_(True), Resource.quantity <= Resource.min_threshold)) or 0
    return DepartmentOut(id=d.id, name=d.name, code=d.code, description=d.description, capacity=d.capacity, status=d.status,
                         patient_count=routing_service.patient_count(db, d.id), total_beds=s["total"],
                         available_beds=s["available"], occupied_beds=s["occupied"], occupancy_pct=s["occupancy_pct"],
                         low_stock_resources=low)


def resource_out(r: Resource) -> ResourceOut:
    return ResourceOut(id=r.id, name=r.name, category=r.category, unit=r.unit, quantity=r.quantity,
                       min_threshold=r.min_threshold, critical_threshold=r.critical_threshold, department_id=r.department_id,
                       department_name=r.department.name if r.department else None, storage_location=r.storage_location,
                       is_active=r.is_active, level=resource_service.stock_level(r), updated_at=r.updated_at)


def transfers_out(db: Session, rows: list[Transfer]) -> list[TransferOut]:
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    pats = {p.id: p.patient_code for p in db.scalars(select(Patient).where(Patient.id.in_({t.patient_id for t in rows})))} if rows else {}
    bed_ids = {t.destination_bed_id for t in rows if t.destination_bed_id}
    beds = {b.id: b.code for b in db.scalars(select(Bed).where(Bed.id.in_(bed_ids)))} if bed_ids else {}
    return [TransferOut(
        id=t.id, patient_id=t.patient_id, patient_code=pats[t.patient_id], source_department_id=t.source_department_id,
        source_department_name=depts.get(t.source_department_id), destination_department_id=t.destination_department_id,
        destination_department_name=depts[t.destination_department_id], destination_bed_id=t.destination_bed_id,
        destination_bed_code=beds.get(t.destination_bed_id), status=t.status, reason=t.reason,
        cancellation_reason=t.cancellation_reason, requested_at=t.requested_at, approved_at=t.approved_at,
        started_at=t.started_at, completed_at=t.completed_at, cancelled_at=t.cancelled_at) for t in rows]


def discharges_out(db: Session, rows: list[Discharge]) -> list[DischargeOut]:
    pats = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_({d.patient_id for d in rows})))} if rows else {}
    return [DischargeOut(
        id=d.id, patient_id=d.patient_id, patient_code=pats[d.patient_id].patient_code,
        department_name=pats[d.patient_id].department.name if pats[d.patient_id].department else None,
        status=d.status, notes=d.notes, cancellation_reason=d.cancellation_reason, requested_at=d.requested_at,
        approved_at=d.approved_at, completed_at=d.completed_at, cancelled_at=d.cancelled_at) for d in rows]
