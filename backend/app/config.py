"""Application configuration with strict fail-fast validation.

Loads configuration from environment variables or .env file using pydantic-settings.
Refuses to start when required secrets are missing, except when STING_ENV=test.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """STING Runtime and Security Settings."""

    # Core Environment
    STING_ENV: str = Field(
        default="development",
        description="Application environment: development | production | test",
    )
    STING_API_KEY: Optional[str] = Field(
        default=None,
        description="Shared API key for write-level API endpoints (X-STING-Key)",
    )
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins for web clients",
    )
    STORAGE_DIR: Path = Field(
        default=Path("./storage"),
        description="Local storage directory for evidence artifacts and reports",
    )

    # TinyFish Web Intelligence & Detonation
    TINYFISH_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for TinyFish agent and web intelligence services",
    )
    AGENT_DAILY_BUDGET: int = Field(
        default=20,
        description="Maximum daily paid detonation agent runs permitted",
    )
    AGENT_MAX_STEPS: int = Field(
        default=40,
        description="Maximum interaction steps for autonomous detonation",
    )
    AGENT_MAX_SECONDS: int = Field(
        default=180,
        description="Maximum timeout in seconds for autonomous detonation run",
    )
    PROXY_COUNTRY: str = Field(
        default="IN",
        description="Proxy country code for detonation sessions (e.g. IN)",
    )
    DETONATION_PROFILE: str = Field(
        default="stealth",
        description="Browser profile for detonation: stealth | lite",
    )

    # Persistence
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/sting_db",
        description="Async SQLAlchemy database connection URL",
    )

    # Cryptographic Evidence Signing
    EVIDENCE_SIGNING_KEY: Optional[str] = Field(
        default=None,
        description="HMAC secret key used to cryptographically seal evidence PDFs",
    )

    # Synthetic Identity (Never use real personal data)
    SYNTHETIC_NAME: str = Field(
        default="Ramesh Kumar",
        description="Synthetic victim name for filling forms",
    )
    SYNTHETIC_EMAIL: str = Field(
        default="ramesh.investigation@example.com",
        description="Synthetic victim email for funnel interactions",
    )
    SYNTHETIC_PHONE: str = Field(
        default="+919876543210",
        description="Synthetic victim phone number for OTP/SMS traps",
    )

    # Pipeline & Investigation Behavior
    DEMO_REPLAY: bool = Field(
        default=False,
        description="Whether to run in demo replay mode with recorded fixtures",
    )
    SITE_REUSE_DAYS: int = Field(
        default=7,
        description="Window in days to reuse previous detonation for known domains",
    )
    PIPELINE_RUNNER: str = Field(
        default="inprocess",
        description="Pipeline execution runner: inprocess | arq",
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("STORAGE_DIR", mode="before")
    @classmethod
    def parse_storage_dir(cls, value: object) -> Path:
        """Ensure STORAGE_DIR is always resolved as a pathlib.Path."""
        if isinstance(value, str):
            return Path(value)
        if isinstance(value, Path):
            return value
        return Path("./storage")

    @model_validator(mode="after")
    def validate_required_settings(self) -> "Settings":
        """Enforces fail-fast configuration validation.

        When STING_ENV != 'test', critical variables must be non-empty strings.
        In test mode, placeholders are automatically populated to allow isolated tests.
        """
        is_test = self.STING_ENV.lower() == "test"

        if is_test:
            # Provide sensible test defaults if missing
            if not self.TINYFISH_API_KEY:
                self.TINYFISH_API_KEY = "test-tinyfish-api-key"
            if not self.STING_API_KEY:
                self.STING_API_KEY = "test-sting-secret-key"
            if not self.EVIDENCE_SIGNING_KEY:
                self.EVIDENCE_SIGNING_KEY = "test-evidence-signing-key-32chars"
            return self

        # Non-test environments must provide real values
        missing_vars: List[str] = []

        if not self.TINYFISH_API_KEY or not self.TINYFISH_API_KEY.strip():
            missing_vars.append("TINYFISH_API_KEY")

        if not self.STING_API_KEY or not self.STING_API_KEY.strip():
            missing_vars.append("STING_API_KEY")

        if not self.EVIDENCE_SIGNING_KEY or not self.EVIDENCE_SIGNING_KEY.strip():
            missing_vars.append("EVIDENCE_SIGNING_KEY")

        if not self.DATABASE_URL or not self.DATABASE_URL.strip():
            missing_vars.append("DATABASE_URL")

        if missing_vars:
            names = ", ".join(missing_vars)
            raise ValueError(
                f"Missing required environment variable: {names}. "
                "Ensure these are set in your environment or .env file, "
                "or set STING_ENV=test for automated testing."
            )

        return self


def get_settings() -> Settings:
    """Instantiate and return the validated Settings singleton."""
    return Settings()
