from fastapi import APIRouter, Depends, Query

from app.api.deps import DB, require
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require("dashboard:read"))])


@router.get("/summary")
def summary(db: DB):
    return dashboard_service.summary(db)


@router.get("/analytics")
def analytics(db: DB, days: int = Query(14, ge=2, le=90)):
    return dashboard_service.analytics(db, days)
