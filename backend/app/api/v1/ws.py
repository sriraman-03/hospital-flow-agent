from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.errors import AppError
from app.core.permissions import has_permission
from app.db.session import SessionLocal
from app.live.manager import manager
from app.api.deps import user_from_token

router = APIRouter(tags=["live"])


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket, token: str = ""):
    """Live change signals only (ids/severity). Clients re-fetch details through the authorised REST API."""
    db = SessionLocal()
    try:
        user = user_from_token(db, token)
        if not has_permission(user.role, "notifications:read"):
            raise AppError("forbidden")
    except AppError:
        await ws.close(code=4401)
        return
    finally:
        db.close()
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings from the client
    except WebSocketDisconnect:
        manager.disconnect(ws)
