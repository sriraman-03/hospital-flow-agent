"""WebSocket fan-out for live notification updates.

Events are queued on the DB session and only published AFTER a successful commit,
so clients never hear about changes that were rolled back.
"""
import asyncio
import logging

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.loop = asyncio.get_running_loop()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.connections.discard(ws)

    async def _broadcast(self, message: dict) -> None:
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:  # dead socket
                self.connections.discard(ws)

    def publish(self, message: dict) -> None:
        """Thread-safe: callable from sync service code running in the threadpool."""
        if not self.connections or self.loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)
        except Exception:
            log.debug("live publish failed", exc_info=True)


manager = ConnectionManager()


def queue_event(db: Session, message: dict) -> None:
    db.info.setdefault("pending_events", []).append(message)


@event.listens_for(Session, "after_commit")
def _flush_events(session: Session) -> None:
    for msg in session.info.pop("pending_events", []):
        manager.publish(msg)


@event.listens_for(Session, "after_rollback")
def _drop_events(session: Session) -> None:
    session.info.pop("pending_events", None)
