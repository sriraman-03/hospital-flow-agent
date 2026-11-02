from fastapi import APIRouter, Depends

from app.api import serializers
from app.api.deps import DB, page_params, require
from app.repositories import beds as repo
from app.repositories.base import paginate
from app.schemas.common import Page, make_page
from app.schemas.hospital import (AssignmentOut, BedAssign, BedCreate, BedMove, BedOut, BedRelease, BedStatusUpdate)
from app.services import bed_service

router = APIRouter(prefix="/beds", tags=["beds"])


@router.get("", response_model=Page[BedOut])
def list_beds(db: DB, _=Depends(require("beds:read")), department_id: int | None = None, status: str | None = None,
              ward: str | None = None, q: str | None = None, paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    items, total = paginate(db, repo.list_stmt(department_id, status, ward, q), page, size)
    return make_page(serializers.beds_out(db, items), total, page, size)


@router.post("", response_model=BedOut, status_code=201)
def create_bed(body: BedCreate, db: DB, user=Depends(require("departments:write"))):
    return serializers.beds_out(db, [bed_service.create_bed(db, user, body.code, body.department_id, body.ward)])[0]


@router.get("/assignments", response_model=Page[AssignmentOut])
def assignment_history(db: DB, _=Depends(require("beds:read")), bed_id: int | None = None, patient_id: int | None = None,
                       paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    items, total = paginate(db, repo.assignment_history_stmt(bed_id, patient_id), page, size)
    return make_page(serializers.assignments_out(db, items), total, page, size)


@router.post("/transfer-bed", response_model=AssignmentOut)
def move_between_beds(body: BedMove, db: DB, user=Depends(require("beds:write"))):
    return serializers.assignments_out(db, [bed_service.move_patient_bed(db, user, body.patient_id, body.to_bed_id)])[0]


@router.patch("/{bed_id}/status", response_model=BedOut)
def set_status(bed_id: int, body: BedStatusUpdate, db: DB, user=Depends(require("beds:write"))):
    return serializers.beds_out(db, [bed_service.set_bed_status(db, user, bed_id, body.status.value)])[0]


@router.post("/{bed_id}/assign", response_model=AssignmentOut)
def assign(bed_id: int, body: BedAssign, db: DB, user=Depends(require("beds:write"))):
    return serializers.assignments_out(db, [bed_service.assign_bed(db, user, bed_id, body.patient_id)])[0]


@router.post("/{bed_id}/release", response_model=BedOut)
def release(bed_id: int, db: DB, body: BedRelease | None = None, user=Depends(require("beds:write"))):
    return serializers.beds_out(db, [bed_service.release_bed(db, user, bed_id, (body.reason if body else "manual"))])[0]
