from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidStateError, NotFoundError, ValidationFailed
from app.db.types import utcnow
from app.models.enums import DischargeStatus, PatientStatus, TransferStatus
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.hospital import Patient
from app.models.user import User
from app.models.workflow import Discharge, Transfer
from app.services import audit_service, bed_service, capacity_service, settings_service
from app.services import notification_service as ns
from sqlalchemy import select

D = DischargeStatus
TRANSITIONS = {
    D.REQUESTED.value: {D.APPROVED.value, D.CANCELLED.value},
    D.APPROVED.value: {D.COMPLETED.value, D.CANCELLED.value},
    D.COMPLETED.value: set(),
    D.CANCELLED.value: set(),
}


def get_discharge(db: Session, discharge_id: int) -> Discharge:
    d = db.get(Discharge, discharge_id)
    if not d:
        raise NotFoundError("Discharge not found")
    return d


def _check(d: Discharge, new: str) -> None:
    if new not in TRANSITIONS.get(d.status, set()):
        raise InvalidStateError(f"Cannot move a discharge from '{d.status}' to '{new}'")


def _notify(db: Session, d: Discharge, p: Patient, title: str, sev: Sev = Sev.INFO) -> None:
    ns.create_notification(
        db, title=title, description=f"Discharge #{d.id} for patient {p.patient_code}: status {d.status}.",
        category=Cat.DISCHARGE, severity=sev, entity_type="discharge", entity_id=d.id, event_key=f"discharge:{d.id}:{d.status}")


def request_discharge(db: Session, actor: User, patient_id: int, notes: str | None) -> Discharge:
    p = db.get(Patient, patient_id)
    if not p:
        raise NotFoundError("Patient not found")
    if p.status != PatientStatus.ADMITTED.value:
        raise InvalidStateError("Only admitted patients can be discharged")
    open_transfer = db.scalar(select(Transfer.id).where(
        Transfer.patient_id == p.id,
        Transfer.status.in_([TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.IN_PROGRESS.value])))
    if open_transfer:
        raise ConflictError("Resolve or cancel the patient's open transfer before requesting discharge")
    d = Discharge(patient_id=p.id, notes=notes, requested_by=actor.id)
    try:
        with db.begin_nested():
            db.add(d)
            db.flush()
    except IntegrityError:
        raise ConflictError("Patient already has an open discharge") from None
    p.status = PatientStatus.DISCHARGE_PENDING.value
    audit_service.log_action(db, actor, "discharge.request", "discharge", d.id, {"patient_id": p.id})
    _notify(db, d, p, f"Discharge requested: {p.patient_code}")
    if not settings_service.get(db, "discharge_requires_approval"):
        d.status, d.approved_by, d.approved_at = D.APPROVED.value, actor.id, utcnow()
        audit_service.log_action(db, actor, "discharge.auto_approve", "discharge", d.id, {"patient_id": p.id})
        _notify(db, d, p, f"Discharge approved: {p.patient_code}", Sev.SUCCESS)
    db.commit()
    return d


def approve(db: Session, actor: User, discharge_id: int) -> Discharge:
    d = get_discharge(db, discharge_id)
    _check(d, D.APPROVED.value)
    p = db.get(Patient, d.patient_id)
    d.status, d.approved_by, d.approved_at = D.APPROVED.value, actor.id, utcnow()
    audit_service.log_action(db, actor, "discharge.approve", "discharge", d.id, {"patient_id": p.id})
    _notify(db, d, p, f"Discharge approved: {p.patient_code}", Sev.SUCCESS)
    db.commit()
    return d


def complete(db: Session, actor: User, discharge_id: int) -> Discharge:
    """One transaction: close discharge, mark patient discharged, release bed."""
    d = get_discharge(db, discharge_id)
    _check(d, D.COMPLETED.value)
    p = db.get(Patient, d.patient_id)
    try:
        dept_id = p.department_id
        bed_service.release_in_txn(db, actor, p.id, "discharge")
        d.status, d.completed_by, d.completed_at = D.COMPLETED.value, actor.id, utcnow()
        p.status, p.discharged_at = PatientStatus.DISCHARGED.value, d.completed_at
        ns.auto_resolve(db, f"patient:{p.id}:needs_bed", "Patient discharged")
        audit_service.log_action(db, actor, "discharge.complete", "discharge", d.id, {"patient_id": p.id})
        _notify(db, d, p, f"Discharge completed: {p.patient_code}", Sev.SUCCESS)
        if dept_id:
            capacity_service.evaluate_department_capacity(db, dept_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return d


def cancel(db: Session, actor: User, discharge_id: int, reason: str) -> Discharge:
    d = get_discharge(db, discharge_id)
    _check(d, D.CANCELLED.value)
    if not reason or not reason.strip():
        raise ValidationFailed("A cancellation reason is required")
    p = db.get(Patient, d.patient_id)
    d.status, d.cancelled_at, d.cancellation_reason = D.CANCELLED.value, utcnow(), reason.strip()
    p.status = PatientStatus.ADMITTED.value
    audit_service.log_action(db, actor, "discharge.cancel", "discharge", d.id, {"patient_id": p.id})
    _notify(db, d, p, f"Discharge cancelled: {p.patient_code}", Sev.WARNING)
    db.commit()
    return d
