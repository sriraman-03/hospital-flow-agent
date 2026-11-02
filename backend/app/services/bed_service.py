from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidStateError, NotFoundError, ValidationFailed
from app.db.types import utcnow
from app.models.enums import BedStatus, DepartmentStatus, PatientStatus
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.hospital import Bed, BedAssignment, Department, Patient
from app.models.user import User
from app.services import audit_service, capacity_service
from app.services import notification_service as ns

MANUAL_STATUSES = {BedStatus.AVAILABLE.value, BedStatus.CLEANING.value, BedStatus.MAINTENANCE.value, BedStatus.UNAVAILABLE.value}
ASSIGNABLE_PATIENT_STATUSES = {PatientStatus.ADMITTED.value, PatientStatus.DISCHARGE_PENDING.value}


def get_bed(db: Session, bed_id: int) -> Bed:
    bed = db.get(Bed, bed_id)
    if not bed:
        raise NotFoundError("Bed not found")
    return bed


def active_assignment_for_patient(db: Session, patient_id: int) -> BedAssignment | None:
    return db.scalar(select(BedAssignment).where(BedAssignment.patient_id == patient_id, BedAssignment.released_at.is_(None)))


def active_assignment_for_bed(db: Session, bed_id: int) -> BedAssignment | None:
    return db.scalar(select(BedAssignment).where(BedAssignment.bed_id == bed_id, BedAssignment.released_at.is_(None)))


def create_bed(db: Session, actor: User, code: str, department_id: int, ward: str) -> Bed:
    if not db.get(Department, department_id):
        raise NotFoundError("Department not found")
    if db.scalar(select(Bed).where(Bed.code == code)):
        raise ConflictError(f"Bed code '{code}' already exists")
    bed = Bed(code=code, department_id=department_id, ward=ward)
    db.add(bed)
    db.flush()
    audit_service.log_action(db, actor, "bed.create", "bed", bed.id, {"department_id": department_id, "ward": ward})
    capacity_service.evaluate_department_capacity(db, department_id)
    db.commit()
    return bed


def assign_in_txn(db: Session, actor: User, bed: Bed, patient: Patient, *, reason_event: str = "assigned") -> BedAssignment:
    """Core assignment rule set. Does NOT commit; callers own the transaction."""
    if patient.status not in ASSIGNABLE_PATIENT_STATUSES:
        raise InvalidStateError("Only admitted patients can be assigned a bed")
    if bed.status != BedStatus.AVAILABLE.value:
        raise ConflictError(f"Bed {bed.code} is not available (status: {bed.status})")
    if patient.department_id != bed.department_id:
        raise ConflictError("Bed belongs to a different department than the patient's current department; use a transfer")
    if active_assignment_for_patient(db, patient.id):
        raise ConflictError("Patient already has an active bed assignment")
    if active_assignment_for_bed(db, bed.id):
        raise ConflictError(f"Bed {bed.code} already has an active patient")

    assignment = BedAssignment(bed_id=bed.id, patient_id=patient.id, assigned_by=actor.id)
    bed.status = BedStatus.OCCUPIED.value
    try:
        with db.begin_nested():  # unique partial indexes are the final guard against concurrent allocation
            db.add(assignment)
            db.flush()
    except IntegrityError:
        raise ConflictError(f"Bed {bed.code} was just allocated by another request") from None

    audit_service.log_action(db, actor, f"bed.{reason_event}", "bed", bed.id,
                             {"patient_id": patient.id, "assignment_id": assignment.id})
    ns.create_notification(
        db, title=f"Bed {bed.code} assigned", description=f"Patient {patient.patient_code} assigned to bed {bed.code}.",
        category=Cat.BED, severity=Sev.INFO, entity_type="bed", entity_id=bed.id,
        event_key=f"bed:assignment:{assignment.id}:assigned")
    ns.auto_resolve(db, f"patient:{patient.id}:needs_bed", "Bed assigned")
    return assignment


def release_in_txn(db: Session, actor: User, patient_id: int, reason: str, *, new_status: str = BedStatus.CLEANING.value) -> Bed | None:
    """Releases the patient's active bed (if any). Does NOT commit."""
    assignment = active_assignment_for_patient(db, patient_id)
    if not assignment:
        return None
    assignment.released_at, assignment.released_by, assignment.release_reason = utcnow(), actor.id, reason
    bed = db.get(Bed, assignment.bed_id)
    bed.status = new_status
    db.flush()
    audit_service.log_action(db, actor, "bed.release", "bed", bed.id, {"patient_id": patient_id, "reason": reason})
    patient = db.get(Patient, patient_id)
    ns.create_notification(
        db, title=f"Bed {bed.code} released", description=f"Bed {bed.code} released ({reason}) and is now {new_status}.",
        category=Cat.BED, severity=Sev.INFO, entity_type="bed", entity_id=bed.id,
        event_key=f"bed:assignment:{assignment.id}:released")
    return bed


def assign_bed(db: Session, actor: User, bed_id: int, patient_id: int) -> BedAssignment:
    bed = get_bed(db, bed_id)
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    try:
        a = assign_in_txn(db, actor, bed, patient)
        capacity_service.evaluate_department_capacity(db, bed.department_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return a


def move_patient_bed(db: Session, actor: User, patient_id: int, to_bed_id: int) -> BedAssignment:
    """Move between beds in the SAME department atomically (cross-department moves use transfers)."""
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    to_bed = get_bed(db, to_bed_id)
    current = active_assignment_for_patient(db, patient_id)
    if not current:
        raise InvalidStateError("Patient has no current bed; use bed assignment instead")
    if current.bed_id == to_bed_id:
        raise ValidationFailed("Patient is already in that bed")
    try:
        release_in_txn(db, actor, patient_id, "reassignment")
        a = assign_in_txn(db, actor, to_bed, patient, reason_event="moved_in")
        capacity_service.evaluate_department_capacity(db, to_bed.department_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return a


def release_bed(db: Session, actor: User, bed_id: int, reason: str = "manual") -> Bed:
    bed = get_bed(db, bed_id)
    assignment = active_assignment_for_bed(db, bed_id)
    if not assignment:
        raise InvalidStateError("Bed has no active patient assignment")
    try:
        release_in_txn(db, actor, assignment.patient_id, reason)
        patient = db.get(Patient, assignment.patient_id)
        if patient and patient.status in ASSIGNABLE_PATIENT_STATUSES:
            ns.create_notification(
                db, title=f"Patient {patient.patient_code} has no bed",
                description="Patient is admitted but currently has no bed assignment.", category=Cat.BED,
                severity=Sev.WARNING, entity_type="patient", entity_id=patient.id, dedup_key=f"patient:{patient.id}:needs_bed")
        capacity_service.evaluate_department_capacity(db, bed.department_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return bed


def set_bed_status(db: Session, actor: User, bed_id: int, status: str) -> Bed:
    bed = get_bed(db, bed_id)
    if status not in MANUAL_STATUSES:
        raise ValidationFailed("Bed status can only be set to available, cleaning, maintenance or unavailable; occupancy is set by assignment")
    if bed.status == BedStatus.OCCUPIED.value:
        raise InvalidStateError("Release the patient before changing the status of an occupied bed")
    old, bed.status = bed.status, status
    audit_service.log_action(db, actor, "bed.status_change", "bed", bed.id, {"from": old, "to": status})
    capacity_service.evaluate_department_capacity(db, bed.department_id)
    db.commit()
    return bed


def ensure_department_open(dept: Department | None) -> Department:
    if not dept:
        raise NotFoundError("Department not found")
    if dept.status == DepartmentStatus.CLOSED.value:
        raise InvalidStateError(f"Department {dept.name} is closed")
    return dept
