from fastapi import APIRouter, Depends
from sqlalchemy import or_, select

from app.api import serializers
from app.api.deps import DB, page_params, require
from app.repositories.base import paginate
from app.models.inventory import Resource, ResourceMovement
from app.schemas.common import Page, make_page
from app.schemas.operations import MovementCreate, MovementOut, ResourceCreate, ResourceOut, ResourceUpdate
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=Page[ResourceOut])
def list_resources(db: DB, _=Depends(require("resources:read")), q: str | None = None, category: str | None = None,
                   department_id: int | None = None, level: str | None = None, include_inactive: bool = False,
                   paging: tuple[int, int] = Depends(page_params)):
    page, size = paging
    stmt = select(Resource)
    if q:
        stmt = stmt.where(or_(Resource.name.ilike(f"%{q}%"), Resource.storage_location.ilike(f"%{q}%")))
    if category:
        stmt = stmt.where(Resource.category == category)
    if department_id:
        stmt = stmt.where(Resource.department_id == department_id)
    if not include_inactive:
        stmt = stmt.where(Resource.is_active.is_(True))
    if level == "critical":
        stmt = stmt.where(Resource.quantity <= Resource.critical_threshold)
    elif level == "low":
        stmt = stmt.where(Resource.quantity <= Resource.min_threshold, Resource.quantity > Resource.critical_threshold)
    elif level == "ok":
        stmt = stmt.where(Resource.quantity > Resource.min_threshold)
    items, total = paginate(db, stmt.order_by(Resource.name, Resource.id), page, size)
    return make_page([serializers.resource_out(r) for r in items], total, page, size)


@router.post("", response_model=ResourceOut, status_code=201)
def create_resource(body: ResourceCreate, db: DB, user=Depends(require("resources:write"))):
    return serializers.resource_out(resource_service.create_resource(db, user, body.model_dump()))


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: DB, _=Depends(require("resources:read"))):
    return serializers.resource_out(resource_service.get_resource(db, resource_id))


@router.patch("/{resource_id}", response_model=ResourceOut)
def update_resource(resource_id: int, body: ResourceUpdate, db: DB, user=Depends(require("resources:write"))):
    return serializers.resource_out(resource_service.update_resource(db, user, resource_id, body.model_dump(exclude_unset=True)))


@router.post("/{resource_id}/movements", response_model=MovementOut, status_code=201)
def add_movement(resource_id: int, body: MovementCreate, db: DB, user=Depends(require("resources:write"))):
    return resource_service.apply_movement(db, user, resource_id, body.movement_type.value, body.quantity, body.reason)


@router.get("/{resource_id}/movements", response_model=Page[MovementOut])
def movement_history(resource_id: int, db: DB, _=Depends(require("resources:read")), paging: tuple[int, int] = Depends(page_params)):
    resource_service.get_resource(db, resource_id)
    page, size = paging
    stmt = select(ResourceMovement).where(ResourceMovement.resource_id == resource_id).order_by(
        ResourceMovement.created_at.desc(), ResourceMovement.id.desc())
    items, total = paginate(db, stmt, page, size)
    return make_page(items, total, page, size)
