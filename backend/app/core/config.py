"""Application Settings and Configuration."""

import os
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base application settings
    PROJECT_NAME: str = "STING — Autonomous Scam Detection & Intelligence Pipeline"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(
        default="development", description="development | staging | production | test"
    )
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "sting-dev-secret-key-32chars-min-length-super-secure"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ]

    # TinyFish API settings
    TINYFISH_API_KEY: Optional[str] = Field(
        default=None, description="API Key for TinyFish web intelligence"
    )
    TINYFISH_BASE_URL: str = "https://agent.tinyfish.ai"
    TINYFISH_SEARCH_URL: str = "https://api.search.tinyfish.ai"
    TINYFISH_FETCH_URL: str = "https://api.fetch.tinyfish.ai"
    TINYFISH_BROWSER_URL: str = "https://api.browser.tinyfish.ai"
    TINYFISH_MOCK_FALLBACK: bool = Field(
        default=True,
        description="Whether to use high-fidelity simulated responses when TINYFISH_API_KEY is not set",
    )
    TINYFISH_MAX_RETRIES: int = 2
    TINYFISH_TIMEOUT_SECONDS: float = 30.0

    # Persistence & Queues
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./sting.db",
        description="SQLAlchemy async database URI (PostgreSQL or SQLite fallback)",
    )
    POSTGRES_DATABASE_URL: Optional[str] = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/sting_db"
    )
    REDIS_URL: str = "redis://localhost:6379/0"

    # Artifact Storage
    EVIDENCE_DIR: str = "./evidence"
    REPORTS_DIR: str = "./reports"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def has_real_tinyfish_key(self) -> bool:
        """Returns True if a non-empty, non-placeholder TinyFish API key is set."""
        if not self.TINYFISH_API_KEY:
            return False
        cleaned = self.TINYFISH_API_KEY.strip()
        return bool(cleaned and cleaned != "your_api_key_here")


# Singleton instance
settings = Settings()

# Ensure storage directories exist
os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
