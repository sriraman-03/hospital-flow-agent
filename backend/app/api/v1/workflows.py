"""Routing recommendations, transfers and discharges."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api import serializers
from app.api.deps import DB, page_params, require
from app.core.errors import ForbiddenError, InvalidStateError, NotFoundError
from app.models.enums import PatientStatus
from app.models.hospital import Patient
from app.models.workflow import Discharge, Transfer
from app.repositories.base import paginate
from app.schemas.common import Page, make_page
from app.schemas.operations import (CancelRequest, DischargeCreate, DischargeOut, RoutingConfirm, RoutingRequest,
                                    TransferCreate, TransferOut)
from app.services import discharge_service, patient_service, routing_service, transfer_service

router = APIRouter(tags=["workflows"])


# ---- routing -----------------------------------------------------------------
@router.post("/routing/recommendations")
def recommendations(body: RoutingRequest, db: DB, _=Depends(require("routing:use"))):
    return routing_service.recommend(db, body.patient_id, body.required_resource_ids)


@router.post("/routing/confirm")
def confirm_routing(body: RoutingConfirm, db: DB, user=Depends(require("transfers:write"))):
    """Human confirmation step. Re-validates against current data, then creates a transfer REQUEST (or pending admission).
    Approval remains a separate, permission-gated step."""
    rec = routing_service.recommend(db, body.patient_id, body.required_resource_ids)
    chosen = next((c for c in rec["candidates"] if c["department_id"] == body.department_id), None)
    if not chosen or not chosen["eligible"]:
        raise InvalidStateError("Selected department is not currently eligible: " + "; ".join(chosen["blockers"] if chosen else ["unknown department"]))
    patient = patient_service.get_patient(db, body.patient_id)
    if patient.status == PatientStatus.ADMITTED.value:
        t = transfer_service.create_transfer(db, user, patient.id, body.department_id, body.bed_id, body.reason or "Routing recommendation confirmed")
        return {"action": "transfer_requested", "transfer_id": t.id}
    patient_service.request_admission(db, user, patient.id, body.department_id)
    return {"action": "admission_requested", "patient_id": patient.id}


# ---- transfers ----------------------------------------------------------------
@router.get("/transfers", response_model=Page[TransferOut])
def list_transfers(db: DB, _=Depends(require("transfers:read")), status: str | None = None, patient_id: int | None = None,
                   paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    stmt = select(Transfer)
    if status:
        stmt = stmt.where(Transfer.status == status)
    if patient_id:
        stmt = stmt.where(Transfer.patient_id == patient_id)
    items, total = paginate(db, stmt.order_by(Transfer.requested_at.desc(), Transfer.id.desc()), page, size)
    return make_page(serializers.transfers_out(db, items), total, page, size)


@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(body: TransferCreate, db: DB, user=Depends(require("transfers:write"))):
    t = transfer_service.create_transfer(db, user, body.patient_id, body.destination_department_id, body.destination_bed_id, body.reason)
    return serializers.transfers_out(db, [t])[0]


@router.get("/transfers/{transfer_id}", response_model=TransferOut)
def get_transfer(transfer_id: int, db: DB, _=Depends(require("transfers:read"))):
    return serializers.transfers_out(db, [transfer_service.get_transfer(db, transfer_id)])[0]


@router.post("/transfers/{transfer_id}/approve", response_model=TransferOut)
def approve_transfer(transfer_id: int, db: DB, user=Depends(require("transfers:approve"))):
    return serializers.transfers_out(db, [transfer_service.approve(db, user, transfer_id)])[0]


@router.post("/transfers/{transfer_id}/start", response_model=TransferOut)
def start_transfer(transfer_id: int, db: DB, user=Depends(require("transfers:write"))):
    return serializers.transfers_out(db, [transfer_service.start(db, user, transfer_id)])[0]


@router.post("/transfers/{transfer_id}/complete", response_model=TransferOut)
def complete_transfer(transfer_id: int, db: DB, user=Depends(require("transfers:write"))):
    return serializers.transfers_out(db, [transfer_service.complete(db, user, transfer_id)])[0]


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferOut)
def cancel_transfer(transfer_id: int, body: CancelRequest, db: DB, user=Depends(require("transfers:write"))):
    return serializers.transfers_out(db, [transfer_service.cancel(db, user, transfer_id, body.reason)])[0]


# ---- discharges -----------------------------------------------------------------
@router.get("/discharges", response_model=Page[DischargeOut])
def list_discharges(db: DB, _=Depends(require("discharges:read")), status: str | None = None, patient_id: int | None = None,
                    paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    stmt = select(Discharge)
    if status:
        stmt = stmt.where(Discharge.status == status)
    if patient_id:
        stmt = stmt.where(Discharge.patient_id == patient_id)
    items, total = paginate(db, stmt.order_by(Discharge.requested_at.desc(), Discharge.id.desc()), page, size)
    return make_page(serializers.discharges_out(db, items), total, page, size)


@router.post("/discharges", response_model=DischargeOut, status_code=201)
def request_discharge(body: DischargeCreate, db: DB, user=Depends(require("discharges:write"))):
    return serializers.discharges_out(db, [discharge_service.request_discharge(db, user, body.patient_id, body.notes)])[0]


@router.get("/discharges/{discharge_id}", response_model=DischargeOut)
def get_discharge(discharge_id: int, db: DB, _=Depends(require("discharges:read"))):
    return serializers.discharges_out(db, [discharge_service.get_discharge(db, discharge_id)])[0]


@router.post("/discharges/{discharge_id}/approve", response_model=DischargeOut)
def approve_discharge(discharge_id: int, db: DB, user=Depends(require("discharges:approve"))):
    return serializers.discharges_out(db, [discharge_service.approve(db, user, discharge_id)])[0]


@router.post("/discharges/{discharge_id}/complete", response_model=DischargeOut)
def complete_discharge(discharge_id: int, db: DB, user=Depends(require("discharges:write"))):
    return serializers.discharges_out(db, [discharge_service.complete(db, user, discharge_id)])[0]


@router.post("/discharges/{discharge_id}/cancel", response_model=DischargeOut)
def cancel_discharge(discharge_id: int, body: CancelRequest, db: DB, user=Depends(require("discharges:write"))):
    return serializers.discharges_out(db, [discharge_service.cancel(db, user, discharge_id, body.reason)])[0]
