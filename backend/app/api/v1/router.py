from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, beds, dashboard, departments, health, notifications, patients, resources, workflows, ws

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, dashboard, patients, departments, beds, resources, workflows, notifications, ai, admin, ws):
    api_router.include_router(module.router)
