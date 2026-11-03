import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidStateError, NotFoundError, ValidationFailed
from app.db.types import utcnow
from app.models.audit import AuditLog
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.enums import PatientStatus
from app.models.hospital import BedAssignment, Department, Patient
from app.models.user import User
from app.models.workflow import Discharge, Transfer
from app.services import audit_service, bed_service, capacity_service
from app.services import notification_service as ns

UPDATABLE = {"first_name", "last_name", "date_of_birth", "phone"}


def get_patient(db: Session, patient_id: int) -> Patient:
    p = db.get(Patient, patient_id)
    if not p:
        raise NotFoundError("Patient not found")
    return p


def register(db: Session, actor: User, data: dict) -> Patient:
    if data["date_of_birth"] > date.today():
        raise ValidationFailed("Date of birth cannot be in the future")
    p = Patient(**data, patient_code=f"tmp-{uuid.uuid4().hex[:28]}", created_by=actor.id)
    db.add(p)
    db.flush()
    p.patient_code = f"PT-{p.id:06d}"
    audit_service.log_action(db, actor, "patient.register", "patient", p.id, {"patient_code": p.patient_code})
    db.commit()
    return p


def update(db: Session, actor: User, patient_id: int, data: dict) -> Patient:
    p = get_patient(db, patient_id)
    changed = []
    for k, v in data.items():
        if k in UPDATABLE and getattr(p, k) != v:
            if k == "date_of_birth" and v > date.today():
                raise ValidationFailed("Date of birth cannot be in the future")
            setattr(p, k, v)
            changed.append(k)
    if changed:
        audit_service.log_action(db, actor, "patient.update", "patient", p.id, {"fields_changed": changed})  # names only, never values
    db.commit()
    return p


def request_admission(db: Session, actor: User, patient_id: int, department_id: int) -> Patient:
    p = get_patient(db, patient_id)
    if p.status not in (PatientStatus.REGISTERED.value, PatientStatus.DISCHARGED.value):
        raise InvalidStateError(f"Cannot request admission for a patient with status '{p.status}'")
    dept = bed_service.ensure_department_open(db.get(Department, department_id))
    p.status, p.requested_department_id = PatientStatus.PENDING_ADMISSION.value, dept.id
    audit_service.log_action(db, actor, "patient.admission_requested", "patient", p.id, {"department_id": dept.id})
    ns.create_notification(
        db, title=f"Admission pending: {p.patient_code}", description=f"Admission to {dept.name} awaiting staff action.",
        category=Cat.PATIENT, severity=Sev.INFO, entity_type="patient", entity_id=p.id,
        event_key=f"patient:{p.id}:admission_requested:{int(utcnow().timestamp())}")
    db.commit()
    return p


def admit(db: Session, actor: User, patient_id: int, department_id: int | None, bed_id: int | None) -> Patient:
    p = get_patient(db, patient_id)
    if p.status not in (PatientStatus.REGISTERED.value, PatientStatus.PENDING_ADMISSION.value, PatientStatus.DISCHARGED.value):
        raise InvalidStateError(f"Patient cannot be admitted from status '{p.status}'")
    dept_id = department_id or p.requested_department_id
    if not dept_id:
        raise ValidationFailed("A department is required to admit a patient")
    dept = bed_service.ensure_department_open(db.get(Department, dept_id))
    try:
        p.status, p.department_id, p.requested_department_id = PatientStatus.ADMITTED.value, dept.id, None
        p.admitted_at, p.discharged_at = utcnow(), None
        db.flush()
        audit_service.log_action(db, actor, "patient.admit", "patient", p.id, {"department_id": dept.id, "bed_id": bed_id})
        ns.create_notification(
            db, title=f"Patient admitted: {p.patient_code}", description=f"Admitted to {dept.name}.",
            category=Cat.PATIENT, severity=Sev.INFO, entity_type="patient", entity_id=p.id,
            event_key=f"patient:{p.id}:admitted:{int(p.admitted_at.timestamp())}")
        if bed_id:
            bed_service.assign_in_txn(db, actor, bed_service.get_bed(db, bed_id), p)
        else:
            ns.create_notification(
                db, title=f"Patient {p.patient_code} needs a bed", description=f"Admitted to {dept.name} without a bed assignment.",
                category=Cat.BED, severity=Sev.WARNING, entity_type="patient", entity_id=p.id, dedup_key=f"patient:{p.id}:needs_bed")
        capacity_service.evaluate_department_capacity(db, dept.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return p


def history(db: Session, patient_id: int) -> list[dict]:
    """Operational timeline (no clinical data)."""
    p = get_patient(db, patient_id)
    events: list[dict] = []
    events.append({"timestamp": p.created_at, "type": "registration", "description": "Patient registered"})
    for a in db.scalars(select(BedAssignment).where(BedAssignment.patient_id == p.id)):
        bed = db.get(bed_service.Bed, a.bed_id)
        events.append({"timestamp": a.assigned_at, "type": "bed_assigned", "description": f"Assigned to bed {bed.code}"})
        if a.released_at:
            events.append({"timestamp": a.released_at, "type": "bed_released",
                           "description": f"Released bed {bed.code} ({a.release_reason})"})
    for t in db.scalars(select(Transfer).where(Transfer.patient_id == p.id)):
        events.append({"timestamp": t.requested_at, "type": "transfer", "description": f"Transfer #{t.id} requested"})
        if t.completed_at:
            events.append({"timestamp": t.completed_at, "type": "transfer", "description": f"Transfer #{t.id} completed"})
        if t.cancelled_at:
            events.append({"timestamp": t.cancelled_at, "type": "transfer", "description": f"Transfer #{t.id} cancelled"})
    for d in db.scalars(select(Discharge).where(Discharge.patient_id == p.id)):
        events.append({"timestamp": d.requested_at, "type": "discharge", "description": f"Discharge #{d.id} requested"})
        if d.completed_at:
            events.append({"timestamp": d.completed_at, "type": "discharge", "description": f"Discharge #{d.id} completed"})
    for log in db.scalars(select(AuditLog).where(AuditLog.entity_type == "patient", AuditLog.entity_id == str(p.id))):
        events.append({"timestamp": log.created_at, "type": "audit", "description": log.action})
    return sorted(events, key=lambda e: e["timestamp"], reverse=True)
