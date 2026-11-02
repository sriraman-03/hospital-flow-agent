from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.types import utcnow
from app.models.audit import AuditLog
from app.models.enums import BedStatus, DischargeStatus, NotificationSeverity, PatientStatus, TransferStatus
from app.models.hospital import Bed, Department, Patient
from app.models.inventory import Resource
from app.models.notification import Notification
from app.models.workflow import Discharge, Transfer
from app.services import capacity_service


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def summary(db: Session) -> dict:
    bed_counts = dict(db.execute(select(Bed.status, func.count()).group_by(Bed.status)).all())
    occupied = bed_counts.get(BedStatus.OCCUPIED.value, 0)
    operational = sum(bed_counts.values()) - bed_counts.get(BedStatus.MAINTENANCE.value, 0) - bed_counts.get(BedStatus.UNAVAILABLE.value, 0)
    low_stock = _count(db, select(func.count()).select_from(Resource).where(
        Resource.is_active.is_(True), Resource.quantity <= Resource.min_threshold))
    return {
        "total_patients": _count(db, select(func.count()).select_from(Patient)),
        "admitted_patients": _count(db, select(func.count()).select_from(Patient).where(
            Patient.status.in_([PatientStatus.ADMITTED.value, PatientStatus.DISCHARGE_PENDING.value]))),
        "available_beds": bed_counts.get(BedStatus.AVAILABLE.value, 0),
        "occupied_beds": occupied,
        "total_beds": sum(bed_counts.values()),
        "occupancy_rate": round(100 * occupied / operational, 1) if operational else 0.0,
        "pending_admissions": _count(db, select(func.count()).select_from(Patient).where(
            Patient.status == PatientStatus.PENDING_ADMISSION.value)),
        "pending_transfers": _count(db, select(func.count()).select_from(Transfer).where(
            Transfer.status.in_([TransferStatus.REQUESTED.value, TransferStatus.APPROVED.value, TransferStatus.IN_PROGRESS.value]))),
        "discharges_in_progress": _count(db, select(func.count()).select_from(Discharge).where(
            Discharge.status.in_([DischargeStatus.REQUESTED.value, DischargeStatus.APPROVED.value]))),
        "low_stock_resources": low_stock,
        "unread_notifications": _count(db, select(func.count()).select_from(Notification).where(Notification.is_read.is_(False))),
        "critical_active_alerts": _count(db, select(func.count()).select_from(Notification).where(
            Notification.severity == NotificationSeverity.CRITICAL.value, Notification.is_resolved.is_(False))),
    }


def analytics(db: Session, days: int = 14) -> dict:
    since = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    occupancy = []
    for d in db.scalars(select(Department).order_by(Department.name)):
        s = capacity_service.department_bed_stats(db, d.id)
        occupancy.append({"department": d.name, "occupied": s["occupied"], "available": s["available"],
                          "cleaning": s["cleaning"], "out_of_service": s["maintenance"] + s["unavailable"],
                          "occupancy_pct": s["occupancy_pct"]})

    admitted = [t for (t,) in db.execute(select(Patient.admitted_at).where(Patient.admitted_at >= since))]
    discharged = [t for (t,) in db.execute(select(Patient.discharged_at).where(Patient.discharged_at >= since))]
    series = []
    for i in range(days):
        day = (since + timedelta(days=i)).date()
        series.append({"date": day.isoformat(),
                       "admissions": sum(1 for t in admitted if t.date() == day),
                       "discharges": sum(1 for t in discharged if t.date() == day)})

    resources = [
        {"id": r.id, "name": r.name, "quantity": r.quantity, "min_threshold": r.min_threshold,
         "critical_threshold": r.critical_threshold, "unit": r.unit}
        for r in db.scalars(select(Resource).where(Resource.is_active.is_(True)).order_by(
            (Resource.quantity * 1.0 / func.nullif(Resource.min_threshold, 0)).asc(), Resource.name).limit(12))
    ]

    sev = dict(db.execute(select(Notification.severity, func.count()).where(Notification.is_resolved.is_(False))
                          .group_by(Notification.severity)).all())
    alerts_by_severity = [{"severity": s.value, "count": sev.get(s.value, 0)} for s in NotificationSeverity]

    critical = [
        {"id": n.id, "title": n.title, "description": n.description, "severity": n.severity, "created_at": n.created_at,
         "entity_type": n.entity_type, "entity_id": n.entity_id, "is_acknowledged": n.is_acknowledged}
        for n in db.scalars(select(Notification).where(
            Notification.severity == NotificationSeverity.CRITICAL.value, Notification.is_resolved.is_(False))
            .order_by(Notification.created_at.desc()).limit(10))
    ]
    recent = [
        {"id": a.id, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
         "actor": a.actor_email, "created_at": a.created_at}
        for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(10))
    ]
    return {"occupancy_by_department": occupancy, "admissions_vs_discharges": series, "resource_levels": resources,
            "alerts_by_severity": alerts_by_severity, "critical_alerts": critical, "recent_activity": recent}
