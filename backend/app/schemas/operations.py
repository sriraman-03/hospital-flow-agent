from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import MovementType
from app.schemas.common import ORM


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field("General", max_length=60)
    unit: str = Field("units", max_length=20)
    quantity: int = Field(0, ge=0)
    min_threshold: int = Field(0, ge=0)
    critical_threshold: int = Field(0, ge=0)
    department_id: int | None = None
    storage_location: str = Field("Main Store", max_length=100)


class ResourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    category: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, max_length=20)
    min_threshold: int | None = Field(None, ge=0)
    critical_threshold: int | None = Field(None, ge=0)
    department_id: int | None = None
    storage_location: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class ResourceOut(BaseModel):
    id: int
    name: str
    category: str
    unit: str
    quantity: int
    min_threshold: int
    critical_threshold: int
    department_id: int | None
    department_name: str | None
    storage_location: str
    is_active: bool
    level: str
    updated_at: datetime


class MovementCreate(BaseModel):
    movement_type: MovementType
    quantity: int = Field(ge=0, le=1_000_000)
    reason: str | None = Field(None, max_length=500)


class MovementOut(ORM):
    id: int
    resource_id: int
    movement_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reason: str | None
    performed_by: int | None
    created_at: datetime


class RoutingRequest(BaseModel):
    patient_id: int
    required_resource_ids: list[int] = []


class RoutingConfirm(BaseModel):
    patient_id: int
    department_id: int
    bed_id: int | None = None
    reason: str | None = Field(None, max_length=500)
    required_resource_ids: list[int] = []


class TransferCreate(BaseModel):
    patient_id: int
    destination_department_id: int
    destination_bed_id: int | None = None
    reason: str | None = Field(None, max_length=500)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TransferOut(BaseModel):
    id: int
    patient_id: int
    patient_code: str
    source_department_id: int | None
    source_department_name: str | None
    destination_department_id: int
    destination_department_name: str
    destination_bed_id: int | None
    destination_bed_code: str | None
    status: str
    reason: str | None
    cancellation_reason: str | None
    requested_at: datetime
    approved_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class DischargeCreate(BaseModel):
    patient_id: int
    notes: str | None = Field(None, max_length=500)


class DischargeOut(BaseModel):
    id: int
    patient_id: int
    patient_code: str
    department_name: str | None
    status: str
    notes: str | None
    cancellation_reason: str | None
    requested_at: datetime
    approved_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class NotificationOut(ORM):
    id: int
    title: str
    description: str
    category: str
    severity: str
    created_at: datetime
    is_read: bool
    read_at: datetime | None
    is_acknowledged: bool
    acknowledged_at: datetime | None
    is_resolved: bool
    resolved_at: datetime | None
    resolution_note: str | None
    entity_type: str | None
    entity_id: int | None
    dedup_key: str | None


class ResolveRequest(BaseModel):
    note: str | None = Field(None, max_length=500)


class AuditOut(ORM):
    id: int
    actor_id: int | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any] | None
    created_at: datetime


class AIRunRequest(BaseModel):
    workflow: str
    patient_id: int | None = None
    question: str | None = Field(None, max_length=500)


class AIExecutionOut(ORM):
    id: int
    workflow: str
    status: str
    input: dict | None
    output: dict | None
    error: str | None
    used_llm: bool
    provider: str | None
    started_at: datetime
    finished_at: datetime | None


class SettingsUpdate(BaseModel):
    values: dict[str, Any]
