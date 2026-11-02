"""Read-only tools the assistant may call. Every value returned here is a DATABASE FACT.
There are deliberately NO write tools: consequential actions need human confirmation through the normal API."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import DischargeStatus, NotificationSeverity, TransferStatus
from app.models.hospital import Department
from app.models.inventory import Resource
from app.models.notification import Notification
from app.models.workflow import Discharge, Transfer
from app.services import capacity_service, dashboard_service, resource_service, routing_service, settings_service


def bed_availability(db: Session) -> list[dict]:
    out = []
    for d in db.scalars(select(Department).order_by(Department.name)):
        s = capacity_service.department_bed_stats(db, d.id)
        out.append({"department_id": d.id, "department": d.name, "status": d.status, "available": s["available"],
                    "occupied": s["occupied"], "cleaning": s["cleaning"], "total": s["total"],
                    "occupancy_pct": s["occupancy_pct"]})
    return out


def capacity_constraints(db: Session) -> list[dict]:
    warn = settings_service.get(db, "occupancy_warning_pct")
    crit = settings_service.get(db, "occupancy_critical_pct")
    rows = []
    for d in bed_availability(db):
        incoming = routing_service.incoming_open_transfers(db, d["department_id"])
        if d["occupancy_pct"] >= warn or d["available"] == 0 or incoming >= d["available"] > 0:
            level = "critical" if d["occupancy_pct"] >= crit or d["available"] == 0 else "warning"
            rows.append({**d, "incoming_open_transfers": incoming, "level": level})
    return rows


def low_stock(db: Session) -> list[dict]:
    rows = []
    for r in db.scalars(select(Resource).where(Resource.is_active.is_(True))):
        lvl = resource_service.stock_level(r)
        if lvl != "ok":
            rows.append({"resource_id": r.id, "name": r.name, "quantity": r.quantity, "unit": r.unit,
                         "min_threshold": r.min_threshold, "critical_threshold": r.critical_threshold,
                         "level": lvl, "location": r.storage_location})
    return sorted(rows, key=lambda x: (x["level"] != "critical", x["name"]))


def pending_workflows(db: Session) -> dict:
    t = db.scalars(select(Transfer).where(Transfer.status.in_(
        [TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.IN_PROGRESS.value])))
    d = db.scalars(select(Discharge).where(Discharge.status.in_(
        [DischargeStatus.REQUESTED.value, DischargeStatus.APPROVED.value])))
    return {
        "transfers": [{"id": x.id, "status": x.status, "requested_at": x.requested_at.isoformat()} for x in t],
        "discharges": [{"id": x.id, "status": x.status, "requested_at": x.requested_at.isoformat()} for x in d],
    }


def open_alerts(db: Session, limit: int = 15) -> list[dict]:
    order = {NotificationSeverity.CRITICAL.value: 0, NotificationSeverity.WARNING.value: 1,
             NotificationSeverity.INFO.value: 2, NotificationSeverity.SUCCESS.value: 3}
    rows = list(db.scalars(select(Notification).where(Notification.is_resolved.is_(False))
                           .order_by(Notification.created_at.desc()).limit(200)))
    rows.sort(key=lambda n: (order.get(n.severity, 9), n.is_acknowledged))
    return [{"id": n.id, "title": n.title, "severity": n.severity, "category": n.category,
             "acknowledged": n.is_acknowledged, "entity_type": n.entity_type, "entity_id": n.entity_id}
            for n in rows[:limit]]


def hospital_summary(db: Session) -> dict:
    return dashboard_service.summary(db)
