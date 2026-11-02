from datetime import datetime

from sqlalchemy import Select, or_, select

from app.models.notification import Notification


def list_stmt(*, q: str | None, category: str | None, severity: str | None, is_read: bool | None,
              is_resolved: bool | None, is_acknowledged: bool | None, date_from: datetime | None,
              date_to: datetime | None) -> Select:
    stmt = select(Notification)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Notification.title.ilike(like), Notification.description.ilike(like)))
    if category:
        stmt = stmt.where(Notification.category == category)
    if severity:
        stmt = stmt.where(Notification.severity == severity)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read.is_(is_read))
    if is_resolved is not None:
        stmt = stmt.where(Notification.is_resolved.is_(is_resolved))
    if is_acknowledged is not None:
        stmt = stmt.where(Notification.is_acknowledged.is_(is_acknowledged))
    if date_from:
        stmt = stmt.where(Notification.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Notification.created_at <= date_to)
    return stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
