from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api import serializers
from app.api.deps import DB, require
from app.core.errors import ConflictError, NotFoundError
from app.models.hospital import Department
from app.schemas.hospital import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services import audit_service, capacity_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: DB, _=Depends(require("departments:read"))):
    return [serializers.department_out(db, d) for d in db.scalars(select(Department).order_by(Department.name))]


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentCreate, db: DB, user=Depends(require("departments:write"))):
    if db.scalar(select(Department).where((Department.name == body.name) | (Department.code == body.code.upper()))):
        raise ConflictError("A department with this name or code already exists")
    d = Department(**{**body.model_dump(), "code": body.code.upper(), "status": body.status.value})
    db.add(d)
    db.flush()
    audit_service.log_action(db, user, "department.create", "department", d.id, {"name": d.name})
    db.commit()
    return serializers.department_out(db, d)


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(department_id: int, db: DB, _=Depends(require("departments:read"))):
    d = db.get(Department, department_id)
    if not d:
        raise NotFoundError("Department not found")
    return serializers.department_out(db, d)


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(department_id: int, body: DepartmentUpdate, db: DB, user=Depends(require("departments:write"))):
    d = db.get(Department, department_id)
    if not d:
        raise NotFoundError("Department not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != d.name and db.scalar(select(Department).where(Department.name == data["name"])):
        raise ConflictError("A department with this name already exists")
    if "status" in data and data["status"] is not None:
        data["status"] = data["status"].value
    for k, v in data.items():
        setattr(d, k, v)
    audit_service.log_action(db, user, "department.update", "department", d.id, {"fields_changed": sorted(data)})
    capacity_service.evaluate_department_capacity(db, d.id)
    db.commit()
    return serializers.department_out(db, d)
