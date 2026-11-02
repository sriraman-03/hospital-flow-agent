from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DB, page_params, require
from app.models.audit import AuditLog
from app.models.user import User
from app.repositories.base import paginate
from app.schemas.auth import PasswordReset, UserCreate, UserOut, UserUpdate
from app.schemas.common import Message, Page, make_page
from app.schemas.operations import AuditOut, SettingsUpdate
from app.services import settings_service, user_service

router = APIRouter(tags=["admin"])


@router.get("/audit-logs", response_model=Page[AuditOut])
def audit_logs(db: DB, _=Depends(require("audit:read")), action: str | None = None, entity_type: str | None = None,
               entity_id: str | None = None, actor_id: int | None = None, paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    items, total = paginate(db, stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), page, size)
    return make_page(items, total, page, size)


@router.get("/users", response_model=list[UserOut])
def list_users(db: DB, _=Depends(require("users:manage"))):
    return list(db.scalars(select(User).order_by(User.full_name)))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, actor=Depends(require("users:manage"))):
    return user_service.create_user(db, actor, email=body.email, full_name=body.full_name, password=body.password,
                                    role=body.role.value, department_id=body.department_id)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DB, actor=Depends(require("users:manage"))):
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        data["role"] = data["role"].value
    return user_service.update_user(db, actor, user_id, data)


@router.post("/users/{user_id}/reset-password", response_model=Message)
def reset_password(user_id: int, body: PasswordReset, db: DB, actor=Depends(require("users:manage"))):
    user_service.reset_password(db, actor, user_id, body.new_password)
    return Message(message="Password reset")


@router.get("/settings")
def get_settings(db: DB, _=Depends(require("settings:read"))):
    return settings_service.get_all(db)


@router.put("/settings")
def put_settings(body: SettingsUpdate, db: DB, actor=Depends(require("settings:manage"))):
    return settings_service.update(db, actor, body.values)
