from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidStateError, NotFoundError, ValidationFailed
from app.db.types import utcnow
from app.models.enums import BedStatus, PatientStatus, TransferStatus
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.hospital import Bed, Department, Patient
from app.models.user import User
from app.models.workflow import Transfer
from app.services import audit_service, bed_service, capacity_service
from app.services import notification_service as ns

S = TransferStatus
TRANSITIONS: dict[str, set[str]] = {
    S.REQUESTED.value: {S.APPROVED.value, S.CANCELLED.value},
    S.APPROVED.value: {S.IN_PROGRESS.value, S.CANCELLED.value},
    S.IN_PROGRESS.value: {S.COMPLETED.value, S.CANCELLED.value},
    S.COMPLETED.value: set(),
    S.CANCELLED.value: set(),
}


def get_transfer(db: Session, transfer_id: int) -> Transfer:
    t = db.get(Transfer, transfer_id)
    if not t:
        raise NotFoundError("Transfer not found")
    return t


def _check_transition(t: Transfer, new: str) -> None:
    if new not in TRANSITIONS.get(t.status, set()):
        raise InvalidStateError(f"Cannot move a transfer from '{t.status}' to '{new}'")


def _validate_destination_bed(db: Session, bed_id: int, dest_dept_id: int) -> Bed:
    bed = bed_service.get_bed(db, bed_id)
    if bed.department_id != dest_dept_id:
        raise ValidationFailed("Destination bed is not in the destination department")
    if bed.status != BedStatus.AVAILABLE.value:
        raise ConflictError(f"Bed {bed.code} is not available (status: {bed.status})")
    return bed


def _notify(db: Session, t: Transfer, patient: Patient, title: str, sev: Sev = Sev.INFO) -> None:
    ns.create_notification(
        db, title=title, description=f"Transfer #{t.id} for patient {patient.patient_code}: status {t.status}.",
        category=Cat.TRANSFER, severity=sev, entity_type="transfer", entity_id=t.id,
        event_key=f"transfer:{t.id}:{t.status}")


def create_transfer(db: Session, actor: User, patient_id: int, destination_department_id: int,
                    destination_bed_id: int | None, reason: str | None) -> Transfer:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    if patient.status != PatientStatus.ADMITTED.value:
        raise InvalidStateError("Only admitted patients (without a pending discharge) can be transferred")
    dest = bed_service.ensure_department_open(db.get(Department, destination_department_id))
    if dest.id == patient.department_id:
        raise ValidationFailed("Destination must differ from the patient's current department")
    if destination_bed_id:
        _validate_destination_bed(db, destination_bed_id, dest.id)
    t = Transfer(patient_id=patient.id, source_department_id=patient.department_id, destination_department_id=dest.id,
                 destination_bed_id=destination_bed_id, reason=reason, requested_by=actor.id)
    try:
        with db.begin_nested():
            db.add(t)
            db.flush()
    except IntegrityError:
        raise ConflictError("Patient already has an open transfer") from None
    audit_service.log_action(db, actor, "transfer.request", "transfer", t.id,
                             {"patient_id": patient.id, "to_department_id": dest.id, "to_bed_id": destination_bed_id})
    _notify(db, t, patient, f"Transfer requested: {patient.patient_code} → {dest.name}")
    db.commit()
    return t


def approve(db: Session, actor: User, transfer_id: int) -> Transfer:
    t = get_transfer(db, transfer_id)
    _check_transition(t, S.APPROVED.value)
    if t.destination_bed_id:
        _validate_destination_bed(db, t.destination_bed_id, t.destination_department_id)
    bed_service.ensure_department_open(db.get(Department, t.destination_department_id))
    t.status, t.approved_by, t.approved_at = S.APPROVED.value, actor.id, utcnow()
    patient = db.get(Patient, t.patient_id)
    audit_service.log_action(db, actor, "transfer.approve", "transfer", t.id, {"patient_id": t.patient_id})
    _notify(db, t, patient, f"Transfer approved: {patient.patient_code}", Sev.SUCCESS)
    db.commit()
    return t


def start(db: Session, actor: User, transfer_id: int) -> Transfer:
    t = get_transfer(db, transfer_id)
    _check_transition(t, S.IN_PROGRESS.value)
    t.status, t.started_at = S.IN_PROGRESS.value, utcnow()
    patient = db.get(Patient, t.patient_id)
    audit_service.log_action(db, actor, "transfer.start", "transfer", t.id, {"patient_id": t.patient_id})
    _notify(db, t, patient, f"Transfer in progress: {patient.patient_code}")
    db.commit()
    return t


def complete(db: Session, actor: User, transfer_id: int) -> Transfer:
    """One transaction: release old bed, move patient, assign new bed, close transfer. All-or-nothing."""
    t = get_transfer(db, transfer_id)
    _check_transition(t, S.COMPLETED.value)
    patient = db.get(Patient, t.patient_id)
    try:
        old_dept = patient.department_id
        bed_service.release_in_txn(db, actor, patient.id, "transfer")
        patient.department_id = t.destination_department_id
        db.flush()
        if t.destination_bed_id:
            bed_service.assign_in_txn(db, actor, bed_service.get_bed(db, t.destination_bed_id), patient)
        else:
            ns.create_notification(
                db, title=f"Patient {patient.patient_code} needs a bed",
                description="Transfer completed without a destination bed.", category=Cat.BED, severity=Sev.WARNING,
                entity_type="patient", entity_id=patient.id, dedup_key=f"patient:{patient.id}:needs_bed")
        t.status, t.completed_at = S.COMPLETED.value, utcnow()
        audit_service.log_action(db, actor, "transfer.complete", "transfer", t.id,
                                 {"patient_id": patient.id, "from_department_id": old_dept, "to_department_id": t.destination_department_id})
        _notify(db, t, patient, f"Transfer completed: {patient.patient_code}", Sev.SUCCESS)
        for d in {old_dept, t.destination_department_id}:
            if d:
                capacity_service.evaluate_department_capacity(db, d)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return t


def cancel(db: Session, actor: User, transfer_id: int, reason: str) -> Transfer:
    t = get_transfer(db, transfer_id)
    _check_transition(t, S.CANCELLED.value)
    if not reason or not reason.strip():
        raise ValidationFailed("A cancellation reason is required")
    t.status, t.cancelled_at, t.cancellation_reason = S.CANCELLED.value, utcnow(), reason.strip()
    patient = db.get(Patient, t.patient_id)
    audit_service.log_action(db, actor, "transfer.cancel", "transfer", t.id, {"patient_id": t.patient_id})
    _notify(db, t, patient, f"Transfer cancelled: {patient.patient_code}", Sev.WARNING)
    db.commit()
    return t
