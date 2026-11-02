"""Role -> permission mapping. Enforced on the backend for every protected route."""
from app.models.enums import Role

ALL = {
    "patients:read", "patients:write",
    "beds:read", "beds:write",
    "resources:read", "resources:write",
    "departments:read", "departments:write",
    "routing:use",
    "transfers:read", "transfers:write", "transfers:approve",
    "discharges:read", "discharges:write", "discharges:approve",
    "notifications:read", "notifications:manage",
    "dashboard:read",
    "ai:use",
    "audit:read",
    "users:manage",
    "settings:read", "settings:manage",
}

READ_ONLY = {p for p in ALL if p.endswith(":read")} - {"audit:read"}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: set(ALL),
    Role.OPERATIONS.value: ALL - {"users:manage", "settings:manage", "audit:read"},
    Role.DEPARTMENT.value: READ_ONLY
    | {"patients:write", "beds:write", "resources:write", "routing:use", "transfers:write",
       "discharges:write", "notifications:manage"},
    Role.VIEWER.value: set(READ_ONLY),
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
