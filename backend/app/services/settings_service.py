from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models.audit import SystemSetting
from app.models.user import User
from app.services import audit_service

# key -> (default, type, min, max)
DEFINITIONS: dict[str, tuple[str, str, float | None, float | None]] = {
    "discharge_requires_approval": ("true", "bool", None, None),
    "occupancy_warning_pct": ("85", "int", 1, 100),
    "occupancy_critical_pct": ("95", "int", 1, 100),
    "routing_weight_availability": ("0.6", "float", 0, 1),
    "routing_weight_occupancy": ("0.4", "float", 0, 1),
}


def _cast(key: str, raw: str):
    _, kind, _, _ = DEFINITIONS[key]
    if kind == "bool":
        return raw.lower() == "true"
    if kind == "int":
        return int(raw)
    return float(raw)


def get_all(db: Session) -> dict:
    stored = {s.key: s.value for s in db.scalars(select(SystemSetting))}
    return {k: _cast(k, stored.get(k, d[0])) for k, d in DEFINITIONS.items()}


def get(db: Session, key: str):
    row = db.get(SystemSetting, key)
    return _cast(key, row.value if row else DEFINITIONS[key][0])


def update(db: Session, actor: User, values: dict) -> dict:
    changed = []
    for key, value in values.items():
        if key not in DEFINITIONS:
            raise ValidationFailed(f"Unknown setting: {key}")
        _, kind, lo, hi = DEFINITIONS[key]
        try:
            if kind == "bool":
                if not isinstance(value, bool):
                    raise ValueError
                text = "true" if value else "false"
            else:
                num = int(value) if kind == "int" else float(value)
                if (lo is not None and num < lo) or (hi is not None and num > hi):
                    raise ValueError
                text = str(num)
        except (TypeError, ValueError):
            raise ValidationFailed(f"Invalid value for {key}") from None
        row = db.get(SystemSetting, key)
        if row:
            row.value, row.updated_by = text, actor.id
        else:
            db.add(SystemSetting(key=key, value=text, updated_by=actor.id))
        changed.append(key)
    merged = {**get_all(db), **{k: _cast(k, "true" if v is True else "false" if v is False else str(v)) for k, v in values.items() if k in DEFINITIONS}}
    if merged["occupancy_warning_pct"] >= merged["occupancy_critical_pct"]:
        db.rollback()
        raise ValidationFailed("occupancy_warning_pct must be lower than occupancy_critical_pct")
    audit_service.log_action(db, actor, "settings.update", "settings", None, {"keys": changed})
    db.commit()
    return get_all(db)
