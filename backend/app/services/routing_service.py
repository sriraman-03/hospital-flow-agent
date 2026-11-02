"""Rule-based patient routing recommendations.

Recommendations are OPERATIONAL (capacity/availability) suggestions, never clinical decisions.
Nothing is changed until authorised staff review and confirm.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import InvalidStateError, NotFoundError
from app.models.enums import DepartmentStatus, PatientStatus, StockLevel, TransferStatus
from app.models.hospital import Department, Patient
from app.models.inventory import Resource
from app.models.workflow import Transfer
from app.services import capacity_service, resource_service, settings_service

OPEN_TRANSFER = [TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.IN_PROGRESS.value]


def patient_count(db: Session, department_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Patient).where(
        Patient.department_id == department_id,
        Patient.status.in_([PatientStatus.ADMITTED.value, PatientStatus.DISCHARGE_PENDING.value]))) or 0


def incoming_open_transfers(db: Session, department_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Transfer).where(
        Transfer.destination_department_id == department_id, Transfer.status.in_(OPEN_TRANSFER))) or 0


def recommend(db: Session, patient_id: int, required_resource_ids: list[int]) -> dict:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    if patient.status in (PatientStatus.DISCHARGED.value, PatientStatus.DISCHARGE_PENDING.value):
        raise InvalidStateError("Routing is not available for discharged or discharge-pending patients")
    if patient.status == PatientStatus.ADMITTED.value and db.scalar(
            select(Transfer.id).where(Transfer.patient_id == patient.id, Transfer.status.in_(OPEN_TRANSFER))):
        raise InvalidStateError("Patient already has an open transfer")

    w_avail = settings_service.get(db, "routing_weight_availability")
    w_occ = settings_service.get(db, "routing_weight_occupancy")
    resources = list(db.scalars(select(Resource).where(Resource.id.in_(required_resource_ids)))) if required_resource_ids else []
    candidates = []
    for dept in db.scalars(select(Department).order_by(Department.name)):
        reasons: list[str] = []
        blockers: list[str] = []
        stats = capacity_service.department_bed_stats(db, dept.id)
        count = patient_count(db, dept.id)
        incoming = incoming_open_transfers(db, dept.id)
        free_beds = stats["available"]
        effective_free = free_beds - incoming

        if dept.id == patient.department_id:
            blockers.append("Patient is already in this department")
        if dept.status == DepartmentStatus.CLOSED.value:
            blockers.append("Department is closed")
        if free_beds <= 0:
            blockers.append("No available beds")
        elif effective_free <= 0:
            blockers.append(f"All {free_beds} available bed(s) are already claimed by {incoming} pending transfer(s)")
        if dept.capacity and count >= dept.capacity:
            blockers.append(f"Department at its configured capacity ({count}/{dept.capacity})")

        for r in resources:
            if r.department_id in (None, dept.id):
                lvl = resource_service.stock_level(r)
                if lvl == StockLevel.CRITICAL.value or r.quantity == 0:
                    blockers.append(f"Required resource '{r.name}' is at critical level ({r.quantity} {r.unit})")
                elif lvl == StockLevel.LOW.value:
                    reasons.append(f"Required resource '{r.name}' is low ({r.quantity} {r.unit})")
                else:
                    reasons.append(f"Required resource '{r.name}' is sufficiently stocked")
            else:
                blockers.append(f"Required resource '{r.name}' is not stocked for this department")

        eligible = not blockers
        score = 0.0
        if eligible:
            avail_ratio = min(1.0, effective_free / max(stats["operational"], 1))
            occ_headroom = 1 - stats["occupancy_pct"] / 100
            score = round(100 * (w_avail * avail_ratio + w_occ * occ_headroom), 1)
            reasons.insert(0, f"{effective_free} bed(s) free after pending transfers; occupancy {stats['occupancy_pct']}%")
            if dept.status == DepartmentStatus.LIMITED.value:
                score = round(score * 0.8, 1)
                reasons.append("Department is in 'limited' status: score reduced, confirm acceptance with the department")
        candidates.append({
            "department_id": dept.id, "department_name": dept.name, "eligible": eligible, "score": score,
            "available_beds": free_beds, "occupancy_pct": stats["occupancy_pct"], "patient_count": count,
            "reasons": reasons, "blockers": blockers,
        })
    candidates.sort(key=lambda c: (not c["eligible"], -c["score"], c["department_name"]))
    return {
        "patient_id": patient.id, "patient_code": patient.patient_code,
        "disclaimer": "Operational capacity suggestions only. Not a clinical decision. Staff must review and confirm.",
        "weights": {"availability": w_avail, "occupancy": w_occ},
        "candidates": candidates,
    }
