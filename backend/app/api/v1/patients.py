from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import serializers
from app.api.deps import DB, page_params, require
from app.repositories import patients as repo
from app.repositories.base import paginate
from app.schemas.common import Page, make_page
from app.schemas.hospital import AdmitRequest, HistoryEvent, PatientCreate, PatientOut, PatientUpdate, RequestAdmission
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=Page[PatientOut])
def list_patients(db: DB, _=Depends(require("patients:read")), q: str | None = None, status: str | None = None,
                  department_id: int | None = None, sort: str = "created_at", order: str = Query("desc", pattern="^(asc|desc)$"),
                  paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    items, total = paginate(db, repo.search_stmt(q, status, department_id, sort, order), page, size)
    return make_page(serializers.patients_out(db, items), total, page, size)


@router.post("", response_model=PatientOut, status_code=201)
def register(body: PatientCreate, db: DB, user=Depends(require("patients:write"))):
    return serializers.patients_out(db, [patient_service.register(db, user, body.model_dump())])[0]


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: DB, _=Depends(require("patients:read"))):
    return serializers.patients_out(db, [patient_service.get_patient(db, patient_id)])[0]


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, body: PatientUpdate, db: DB, user=Depends(require("patients:write"))):
    p = patient_service.update(db, user, patient_id, body.model_dump(exclude_unset=True))
    return serializers.patients_out(db, [p])[0]


@router.post("/{patient_id}/request-admission", response_model=PatientOut)
def request_admission(patient_id: int, body: RequestAdmission, db: DB, user=Depends(require("patients:write"))):
    return serializers.patients_out(db, [patient_service.request_admission(db, user, patient_id, body.department_id)])[0]


@router.post("/{patient_id}/admit", response_model=PatientOut)
def admit(patient_id: int, body: AdmitRequest, db: DB, user=Depends(require("patients:write"))):
    return serializers.patients_out(db, [patient_service.admit(db, user, patient_id, body.department_id, body.bed_id)])[0]


@router.get("/{patient_id}/history", response_model=list[HistoryEvent])
def history(patient_id: int, db: DB, _=Depends(require("patients:read"))):
    return patient_service.history(db, patient_id)
