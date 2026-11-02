from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import InvalidStateError, NotFoundError
from app.db.types import utcnow
from app.live.manager import queue_event
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.notification import Notification
from app.models.user import User
from app.services import audit_service


def _find_open(db: Session, dedup_key: str) -> Notification | None:
    return db.scalar(select(Notification).where(Notification.dedup_key == dedup_key, Notification.is_resolved.is_(False)))


def create_notification(
    db: Session,
    *,
    title: str,
    description: str = "",
    category: Cat,
    severity: Sev,
    entity_type: str | None = None,
    entity_id: int | None = None,
    dedup_key: str | None = None,
    event_key: str | None = None,
) -> Notification:
    """Creates a notification inside the caller's transaction.

    - event_key: idempotency. The same business event never produces two notifications.
    - dedup_key: at most one UNRESOLVED notification per key (e.g. the same low-stock condition).
    Descriptions must not contain patient names; use internal patient codes only.
    """
    if event_key:
        existing = db.scalar(select(Notification).where(Notification.event_key == event_key))
        if existing:
            return existing
    if dedup_key:
        existing = _find_open(db, dedup_key)
        if existing:
            return existing

    n = Notification(
        title=title, description=description, category=category.value, severity=severity.value,
        entity_type=entity_type, entity_id=entity_id, dedup_key=dedup_key, event_key=event_key,
    )
    try:
        with db.begin_nested():  # savepoint: a concurrent duplicate must not poison the outer transaction
            db.add(n)
            db.flush()
    except IntegrityError:
        existing = (event_key and db.scalar(select(Notification).where(Notification.event_key == event_key))) or (
            dedup_key and _find_open(db, dedup_key)
        )
        if existing:
            return existing
        raise
    queue_event(db, {"type": "notification.created", "id": n.id, "severity": n.severity, "category": n.category})
    return n


def auto_resolve(db: Session, dedup_key: str, note: str) -> bool:
    """System-driven resolution (e.g. stock recovered). Returns True if something was resolved."""
    n = _find_open(db, dedup_key)
    if not n:
        return False
    n.is_resolved, n.resolved_at, n.resolution_note = True, utcnow(), note
    n.resolved_by = None
    queue_event(db, {"type": "notification.updated", "id": n.id})
    return True


def _get(db: Session, notification_id: int) -> Notification:
    n = db.get(Notification, notification_id)
    if not n:
        raise NotFoundError("Notification not found")
    return n


def get_notification(db: Session, notification_id: int) -> Notification:
    return _get(db, notification_id)


def set_read(db: Session, notification_id: int, read: bool) -> Notification:
    n = _get(db, notification_id)
    n.is_read, n.read_at = read, (utcnow() if read else None)
    queue_event(db, {"type": "notification.updated", "id": n.id})
    db.commit()
    return n


def mark_all_read(db: Session) -> int:
    result = db.execute(
        update(Notification).where(Notification.is_read.is_(False)).values(is_read=True, read_at=utcnow())
    )
    queue_event(db, {"type": "notification.bulk_read"})
    db.commit()
    return result.rowcount or 0


def acknowledge(db: Session, actor: User, notification_id: int) -> Notification:
    n = _get(db, notification_id)
    if n.is_resolved:
        raise InvalidStateError("Notification is already resolved")
    if not n.is_acknowledged:
        n.is_acknowledged, n.acknowledged_by, n.acknowledged_at = True, actor.id, utcnow()
        if not n.is_read:
            n.is_read, n.read_at = True, utcnow()
        audit_service.log_action(db, actor, "notification.acknowledge", "notification", n.id,
                                 {"severity": n.severity, "category": n.category})
        queue_event(db, {"type": "notification.updated", "id": n.id})
    db.commit()
    return n


def resolve(db: Session, actor: User, notification_id: int, note: str | None) -> Notification:
    """Resolving closes the alert record. It does NOT fix the underlying issue; the next
    business event re-evaluates the condition and can raise a fresh alert if it persists."""
    n = _get(db, notification_id)
    if n.is_resolved:
        raise InvalidStateError("Notification is already resolved")
    n.is_resolved, n.resolved_by, n.resolved_at, n.resolution_note = True, actor.id, utcnow(), note
    if not n.is_read:
        n.is_read, n.read_at = True, utcnow()
    audit_service.log_action(db, actor, "notification.resolve", "notification", n.id,
                             {"severity": n.severity, "category": n.category, "has_note": bool(note)})
    queue_event(db, {"type": "notification.updated", "id": n.id})
    db.commit()
    return n


def unread_counts(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(Notification).where(Notification.is_read.is_(False))) or 0
    critical = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.severity == Sev.CRITICAL.value, Notification.is_resolved.is_(False))
    ) or 0
    rows = db.execute(
        select(Notification.category, func.count()).where(Notification.is_read.is_(False)).group_by(Notification.category)
    ).all()
    return {"unread": total, "critical_active": critical, "by_category": {c: n for c, n in rows}}


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
