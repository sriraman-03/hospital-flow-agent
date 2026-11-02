import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hospital Flow Agent"
    environment: str = "development"
    database_url: str = "sqlite:///./hospital_flow.db"
    secret_key: str = ""
    access_token_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:5173"
    seed_user_password: str = ""

    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: int = 30
    mcp_server_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider.lower() in {"anthropic", "openai"} and bool(self.llm_api_key and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.secret_key:
        if s.is_production:
            raise RuntimeError("SECRET_KEY must be set when ENVIRONMENT=production")
        s.secret_key = secrets.token_urlsafe(64)
        log.warning("SECRET_KEY not set: using an ephemeral development key (tokens reset on restart).")
    return s
