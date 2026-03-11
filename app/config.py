"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration for instagram_service.

    All values can be overridden via environment variables or a .env file.
    """

    # ── Meta / Instagram ────────────────────────────────────────────────────
    meta_app_id: str = ""
    meta_app_secret: str = ""
    access_token: str = ""
    instagram_business_id: str = ""
    page_id: str = ""

    # ── LLM ─────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    # Provider to use: "openai" | "deepseek" | "openrouter"
    llm_provider: str = "openai"

    # ── MinIO ────────────────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "instagram-service"
    minio_secure: bool = False

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Scheduler ────────────────────────────────────────────────────────────
    # Comma-separated posting hours in 24-h format, e.g. "9,12,18,20"
    posting_hours: str = "9,12,18,20"

    # ── App ──────────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
