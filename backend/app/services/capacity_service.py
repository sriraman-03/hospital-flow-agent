"""Department capacity alerts, raised from real bed events."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import BedStatus, NotificationCategory, NotificationSeverity
from app.models.hospital import Bed, Department
from app.services import notification_service as ns
from app.services import settings_service


def department_bed_stats(db: Session, department_id: int) -> dict:
    rows = db.execute(select(Bed.status, func.count()).where(Bed.department_id == department_id).group_by(Bed.status)).all()
    counts = {s: 0 for s in (m.value for m in BedStatus)}
    counts.update({s: n for s, n in rows})
    total = sum(counts.values())
    operational = total - counts["maintenance"] - counts["unavailable"]
    occupancy = round(100 * counts["occupied"] / operational, 1) if operational else 0.0
    return {"total": total, "operational": operational, "occupancy_pct": occupancy, **counts}


def evaluate_department_capacity(db: Session, department_id: int) -> None:
    dept = db.get(Department, department_id)
    if not dept:
        return
    stats = department_bed_stats(db, department_id)
    warn = settings_service.get(db, "occupancy_warning_pct")
    crit = settings_service.get(db, "occupancy_critical_pct")
    key_c, key_w = f"dept:{department_id}:occupancy:critical", f"dept:{department_id}:occupancy:warning"
    pct = stats["occupancy_pct"]
    if stats["operational"] == 0:
        return
    if pct >= crit:
        ns.auto_resolve(db, key_w, "Escalated to critical occupancy")
        ns.create_notification(
            db, title=f"{dept.name}: critical bed occupancy",
            description=f"Occupancy is {pct}% ({stats['occupied']} of {stats['operational']} operational beds in use).",
            category=NotificationCategory.BED, severity=NotificationSeverity.CRITICAL,
            entity_type="department", entity_id=dept.id, dedup_key=key_c)
    elif pct >= warn:
        ns.auto_resolve(db, key_c, "Occupancy dropped below critical level")
        ns.create_notification(
            db, title=f"{dept.name}: high bed occupancy",
            description=f"Occupancy is {pct}% ({stats['occupied']} of {stats['operational']} operational beds in use).",
            category=NotificationCategory.BED, severity=NotificationSeverity.WARNING,
            entity_type="department", entity_id=dept.id, dedup_key=key_w)
    else:
        a = ns.auto_resolve(db, key_c, "Occupancy returned to normal")
        b = ns.auto_resolve(db, key_w, "Occupancy returned to normal")
        if a or b:
            ns.create_notification(
                db, title=f"{dept.name}: occupancy back to normal",
                description=f"Occupancy is now {pct}%.", category=NotificationCategory.BED,
                severity=NotificationSeverity.SUCCESS, entity_type="department", entity_id=dept.id,
                event_key=f"dept:{dept.id}:occupancy:recovered:{int(pct)}:{int(__import__('time').time() // 60)}")
