from enum import StrEnum


class Role(StrEnum):
    ADMIN = "administrator"
    OPERATIONS = "operations_staff"
    DEPARTMENT = "department_staff"
    VIEWER = "viewer"


class PatientStatus(StrEnum):
    REGISTERED = "registered"
    PENDING_ADMISSION = "pending_admission"
    ADMITTED = "admitted"
    DISCHARGE_PENDING = "discharge_pending"
    DISCHARGED = "discharged"


class DepartmentStatus(StrEnum):
    ACTIVE = "active"
    LIMITED = "limited"  # accepting only with approval / reduced capacity
    CLOSED = "closed"


class BedStatus(StrEnum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"
    UNAVAILABLE = "unavailable"


class MovementType(StrEnum):
    ADDITION = "addition"
    DEDUCTION = "deduction"
    ADJUSTMENT = "adjustment"  # sets an absolute quantity


class StockLevel(StrEnum):
    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"


class TransferStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DischargeStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class NotificationCategory(StrEnum):
    PATIENT = "patient"
    BED = "bed"
    RESOURCE = "resource"
    ROUTING = "routing"
    TRANSFER = "transfer"
    DISCHARGE = "discharge"
    AI = "ai"
    SYSTEM = "system"


class NotificationSeverity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def check_in(column: str, enum_cls: type[StrEnum], name: str):
    from sqlalchemy import CheckConstraint

    values = ", ".join(f"'{m.value}'" for m in enum_cls)
    return CheckConstraint(f"{column} IN ({values})", name=name)
