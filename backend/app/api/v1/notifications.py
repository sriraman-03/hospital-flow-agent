from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import DB, page_params, require
from app.repositories import notifications as repo
from app.repositories.base import paginate
from app.schemas.common import Message, Page, make_page
from app.schemas.operations import NotificationOut, ResolveRequest
from app.services import notification_service as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut])
def list_notifications(db: DB, _=Depends(require("notifications:read")), q: str | None = None, category: str | None = None,
                       severity: str | None = None, is_read: bool | None = None, is_resolved: bool | None = None,
                       is_acknowledged: bool | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                       paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    stmt = repo.list_stmt(q=q, category=category, severity=severity, is_read=is_read, is_resolved=is_resolved,
                          is_acknowledged=is_acknowledged, date_from=date_from, date_to=date_to)
    items, total = paginate(db, stmt, page, size)
    return make_page(items, total, page, size)


@router.get("/unread-count")
def unread_count(db: DB, _=Depends(require("notifications:read"))):
    return svc.unread_counts(db)


@router.post("/read-all")
def read_all(db: DB, _=Depends(require("notifications:manage"))):
    return {"updated": svc.mark_all_read(db)}


@router.get("/{notification_id}", response_model=NotificationOut)
def get_notification(notification_id: int, db: DB, _=Depends(require("notifications:read"))):
    return svc.get_notification(db, notification_id)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: DB, _=Depends(require("notifications:manage"))):
    return svc.set_read(db, notification_id, True)


@router.post("/{notification_id}/unread", response_model=NotificationOut)
def mark_unread(notification_id: int, db: DB, _=Depends(require("notifications:manage"))):
    return svc.set_read(db, notification_id, False)


@router.post("/{notification_id}/acknowledge", response_model=NotificationOut)
def acknowledge(notification_id: int, db: DB, user=Depends(require("notifications:manage"))):
    return svc.acknowledge(db, user, notification_id)


@router.post("/{notification_id}/resolve", response_model=NotificationOut)
def resolve(notification_id: int, body: ResolveRequest, db: DB, user=Depends(require("notifications:manage"))):
    return svc.resolve(db, user, notification_id, body.note)
