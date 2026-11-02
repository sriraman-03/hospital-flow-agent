import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.live import manager as _live  # noqa: F401  (registers post-commit event publisher)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings()  # fail fast on bad config (e.g. missing SECRET_KEY in production)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name, version="1.0.0", lifespan=lifespan,
        description="Hospital operations management API. Operational support only; not a clinical system.",
        docs_url="/docs", openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
