from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidStateError, NotFoundError, ValidationFailed
from app.models.enums import MovementType, StockLevel
from app.models.enums import NotificationCategory as Cat
from app.models.enums import NotificationSeverity as Sev
from app.models.hospital import Department
from app.models.inventory import Resource, ResourceMovement
from app.models.user import User
from app.services import audit_service
from app.services import notification_service as ns


def stock_level(r: Resource) -> str:
    if r.quantity <= r.critical_threshold:
        return StockLevel.CRITICAL.value
    if r.quantity <= r.min_threshold:
        return StockLevel.LOW.value
    return StockLevel.OK.value


def get_resource(db: Session, resource_id: int) -> Resource:
    r = db.get(Resource, resource_id)
    if not r:
        raise NotFoundError("Resource not found")
    return r


def _validate_thresholds(min_t: int, crit_t: int) -> None:
    if min_t < 0 or crit_t < 0:
        raise ValidationFailed("Thresholds cannot be negative")
    if crit_t > min_t:
        raise ValidationFailed("Critical threshold cannot exceed the minimum (low) threshold")


def evaluate_stock_alert(db: Session, r: Resource, trigger: str) -> None:
    """Raises/escalates/resolves stock alerts. One unresolved alert per condition (dedup keys)."""
    level = stock_level(r)
    low_key, crit_key = f"resource:{r.id}:low", f"resource:{r.id}:critical"
    where = r.storage_location
    if level == StockLevel.CRITICAL.value:
        ns.auto_resolve(db, low_key, "Escalated to critical stock level")
        ns.create_notification(
            db, title=f"Critical stock: {r.name}", description=f"{r.quantity} {r.unit} left at {where} (critical at {r.critical_threshold}).",
            category=Cat.RESOURCE, severity=Sev.CRITICAL, entity_type="resource", entity_id=r.id, dedup_key=crit_key)
    elif level == StockLevel.LOW.value:
        ns.auto_resolve(db, crit_key, "Stock improved to low level")
        ns.create_notification(
            db, title=f"Low stock: {r.name}", description=f"{r.quantity} {r.unit} left at {where} (minimum {r.min_threshold}).",
            category=Cat.RESOURCE, severity=Sev.WARNING, entity_type="resource", entity_id=r.id, dedup_key=low_key)
    else:
        a = ns.auto_resolve(db, low_key, "Stock recovered to a safe level")
        b = ns.auto_resolve(db, crit_key, "Stock recovered to a safe level")
        if a or b:  # recovery tracking
            ns.create_notification(
                db, title=f"Stock recovered: {r.name}", description=f"{r.quantity} {r.unit} now available at {where}.",
                category=Cat.RESOURCE, severity=Sev.SUCCESS, entity_type="resource", entity_id=r.id,
                event_key=f"resource:{r.id}:recovered:{trigger}")


def create_resource(db: Session, actor: User, data: dict) -> Resource:
    _validate_thresholds(data["min_threshold"], data["critical_threshold"])
    if data.get("department_id") and not db.get(Department, data["department_id"]):
        raise NotFoundError("Department not found")
    if db.scalar(select(Resource).where(Resource.name == data["name"], Resource.storage_location == data["storage_location"])):
        raise ConflictError("A resource with this name already exists at this storage location")
    r = Resource(**data)
    db.add(r)
    db.flush()
    if r.quantity:
        db.add(ResourceMovement(resource_id=r.id, movement_type=MovementType.ADDITION.value, quantity_change=r.quantity,
                                quantity_before=0, quantity_after=r.quantity, reason="Initial stock", performed_by=actor.id))
    audit_service.log_action(db, actor, "resource.create", "resource", r.id, {"name": r.name, "initial_quantity": r.quantity})
    evaluate_stock_alert(db, r, f"create{r.id}")
    db.commit()
    return r


def update_resource(db: Session, actor: User, resource_id: int, data: dict) -> Resource:
    r = get_resource(db, resource_id)
    if "quantity" in data:
        raise ValidationFailed("Change quantity through stock movements so history is preserved")
    min_t = data.get("min_threshold", r.min_threshold)
    crit_t = data.get("critical_threshold", r.critical_threshold)
    _validate_thresholds(min_t, crit_t)
    if data.get("department_id") and not db.get(Department, data["department_id"]):
        raise NotFoundError("Department not found")
    for k, v in data.items():
        setattr(r, k, v)
    db.flush()
    audit_service.log_action(db, actor, "resource.update", "resource", r.id, {"fields_changed": sorted(data)})
    evaluate_stock_alert(db, r, f"edit{int(r.updated_at.timestamp() * 1000) if r.updated_at else 0}")
    db.commit()
    return r


def apply_movement(db: Session, actor: User, resource_id: int, movement_type: str, quantity: int, reason: str | None) -> ResourceMovement:
    r = get_resource(db, resource_id)
    if not r.is_active:
        raise InvalidStateError("Resource is inactive")
    if movement_type == MovementType.ADJUSTMENT.value:
        if quantity < 0:
            raise ValidationFailed("Adjusted quantity cannot be negative")
        if not reason:
            raise ValidationFailed("A reason is required for stock adjustments")
        before = r.quantity
        db.execute(update(Resource).where(Resource.id == r.id).values(quantity=quantity))
        after = quantity
    else:
        if quantity <= 0:
            raise ValidationFailed("Quantity must be greater than zero")
        # Atomic guarded UPDATE: prevents negative stock and lost updates under concurrency.
        stmt = update(Resource).where(Resource.id == r.id)
        if movement_type == MovementType.DEDUCTION.value:
            stmt = stmt.where(Resource.quantity >= quantity).values(quantity=Resource.quantity - quantity)
        elif movement_type == MovementType.ADDITION.value:
            stmt = stmt.values(quantity=Resource.quantity + quantity)
        else:
            raise ValidationFailed("Unknown movement type")
        result = db.execute(stmt)
        if result.rowcount == 0:
            db.rollback()
            raise InvalidStateError("Insufficient stock for this deduction")
        db.refresh(r)
        after = r.quantity
        before = after - quantity if movement_type == MovementType.ADDITION.value else after + quantity
    db.refresh(r)
    m = ResourceMovement(resource_id=r.id, movement_type=movement_type, quantity_change=after - before,
                         quantity_before=before, quantity_after=after, reason=reason, performed_by=actor.id)
    db.add(m)
    db.flush()
    audit_service.log_action(db, actor, "resource.stock_movement", "resource", r.id,
                             {"type": movement_type, "change": after - before, "before": before, "after": after})
    evaluate_stock_alert(db, r, f"mv{m.id}")
    db.commit()
    return m
