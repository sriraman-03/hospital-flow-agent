from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BedStatus, DepartmentStatus
from app.schemas.common import ORM


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    date_of_birth: date
    phone: str | None = Field(None, max_length=32)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class PatientUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=80)
    last_name: str | None = Field(None, min_length=1, max_length=80)
    date_of_birth: date | None = None
    phone: str | None = Field(None, max_length=32)


class PatientOut(ORM):
    id: int
    patient_code: str
    first_name: str
    last_name: str
    date_of_birth: date
    phone: str | None
    status: str
    department_id: int | None
    department_name: str | None = None
    requested_department_id: int | None
    bed_id: int | None = None
    bed_code: str | None = None
    admitted_at: datetime | None
    discharged_at: datetime | None
    created_at: datetime


class AdmitRequest(BaseModel):
    department_id: int | None = None
    bed_id: int | None = None


class RequestAdmission(BaseModel):
    department_id: int


class HistoryEvent(BaseModel):
    timestamp: datetime
    type: str
    description: str


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    description: str | None = None
    capacity: int = Field(0, ge=0)
    status: DepartmentStatus = DepartmentStatus.ACTIVE


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    capacity: int | None = Field(None, ge=0)
    status: DepartmentStatus | None = None


class DepartmentOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    capacity: int
    status: str
    patient_count: int
    total_beds: int
    available_beds: int
    occupied_beds: int
    occupancy_pct: float
    low_stock_resources: int


class BedCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    department_id: int
    ward: str = Field("General", min_length=1, max_length=60)


class BedStatusUpdate(BaseModel):
    status: BedStatus


class BedAssign(BaseModel):
    patient_id: int


class BedMove(BaseModel):
    patient_id: int
    to_bed_id: int


class BedRelease(BaseModel):
    reason: str = "manual"


class BedOut(BaseModel):
    id: int
    code: str
    department_id: int
    department_name: str
    ward: str
    status: str
    patient_id: int | None = None
    patient_code: str | None = None


class AssignmentOut(BaseModel):
    id: int
    bed_id: int
    bed_code: str
    patient_id: int
    patient_code: str
    assigned_at: datetime
    released_at: datetime | None
    release_reason: str | None
