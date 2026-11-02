from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User

# Never persist these in audit metadata (credentials, tokens, direct patient identifiers).
BLOCKED_KEYS = {
    "password", "new_password", "current_password", "hashed_password", "token", "access_token",
    "first_name", "last_name", "date_of_birth", "phone", "email",
}


def _sanitize(details: dict | None) -> dict | None:
    if not details:
        return None
    return {k: v for k, v in details.items() if k.lower() not in BLOCKED_KEYS}


def log_action(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Adds an audit row to the CURRENT transaction (committed atomically with the business change)."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=_sanitize(details),
    )
    db.add(entry)
    return entry
