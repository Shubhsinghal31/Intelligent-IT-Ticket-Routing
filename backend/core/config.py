"""
Application configuration loaded from environment variables.

Uses Pydantic Settings for type-safe config with automatic .env loading.
All settings are validated at app startup — invalid config crashes early.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # =====================================================
    # Pydantic settings configuration
    # =====================================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # =====================================================
    # Application
    # =====================================================
    APP_NAME: str = "helpdesk-ai"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "0.1.0"

    # =====================================================
    # FastAPI Server
    # =====================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # =====================================================
    # Database (PostgreSQL)
    # =====================================================
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "helpdesk_ai"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = Field(..., description="Postgres password — required")
    DATABASE_URL: PostgresDsn

    # Connection pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False  # set True to log all SQL (dev debugging)

    # =====================================================
    # JWT Authentication (used in Milestone 3)
    # =====================================================
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # =====================================================
    # Logging
    # =====================================================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    # =====================================================
    # Rate limiting (Milestone 10) — brute-force protection
    # =====================================================
    # Strings use slowapi/limits syntax: "<count>/<period>"
    # (period is one of second, minute, hour, day).
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_FORGOT_PASSWORD: str = "3/minute"

    # =====================================================
    # Password reset (Forgot Password flow)
    # =====================================================
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # =====================================================
    # Outbound email (SMTP) — see backend/core/email.py
    # =====================================================
    # All optional and default to None/unset: if SMTP_HOST is empty,
    # emails are logged instead of sent (see backend/core/email.py).
    # This keeps local dev working without any mail server configured.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    # =====================================================
    # CORS
    # =====================================================
    FRONTEND_URL: str = "http://localhost:8501"

    # Stored as a raw comma-separated STRING, not list[str].
    #
    # pydantic-settings tries to JSON-decode any list-typed field's env var
    # value before any @field_validator runs (even mode="before" ones — the
    # JSON decode happens in the settings SOURCE, a layer earlier than field
    # validation). That's fine for a local .env with a real JSON array, but
    # Render's Blueprint spec has no variable interpolation, so the only way
    # to hand this service the frontend's URL is a single fromService/
    # envVarKey reference (see render.yaml) that resolves to one plain
    # string like "https://helpdesk-ai-frontend.onrender.com" — not valid
    # JSON, so list[str] would crash at startup with a SettingsError before
    # any of our own code ran. Keeping the field a plain str sidesteps that
    # earlier JSON-decode step entirely; cors_origins_list below does the
    # comma-splitting ourselves, on our own schedule.
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split CORS_ORIGINS into the list CORSMiddleware expects."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # =====================================================
    # ML
    # =====================================================
    ML_MODEL_PATH: str = "ml/models/"
    ML_PRIORITY_MODEL: str = "priority_classifier.pkl"
    ML_DEPARTMENT_MODEL: str = "department_classifier.pkl"
    ML_SLA_MODEL: str = "sla_predictor.pkl"

    # =====================================================
    # Ticket attachments
    # =====================================================
    # Local disk for now — documented limitation: Render's filesystem is
    # ephemeral across redeploys, so this will need to move to S3-compatible
    # object storage before a real production deployment (Milestone 14).
    # file_path stored in the DB is always relative to this root, never an
    # absolute path — that's what makes swapping storage backends later a
    # one-file change (AttachmentService) instead of a data migration.
    ATTACHMENTS_STORAGE_PATH: str = "uploads/attachments"

    # Must match the DB CHECK constraint in
    # database/migrations/008_create_attachments_table.sql
    # (chk_attachments_file_size_max) — kept in sync deliberately so a
    # too-large upload is always rejected with a clear 422 from the service
    # layer, not an opaque IntegrityError from the database.
    ATTACHMENTS_MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Allowlist, not a denylist — safer default for arbitrary file upload.
    # Deliberately excludes anything executable or that a browser might
    # render/execute (.exe, .sh, .js, .html, .svg — SVG can carry embedded
    # scripts). Extend this list only for formats you've actually decided
    # to support, never just to unblock one user's file.
    ATTACHMENTS_ALLOWED_MIME_TYPES: list[str] = [
        "image/png",
        "image/jpeg",
        "image/gif",
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    ]

    # =====================================================
    # Computed properties
    # =====================================================
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def log_file_full_path(self) -> Path:
        """Ensure log directory exists and return absolute path."""
        path = Path(self.LOG_FILE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def attachments_storage_full_path(self) -> Path:
        """Ensure the attachments root directory exists and return it."""
        path = Path(self.ATTACHMENTS_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret isn't a placeholder value."""
        weak_values = {
            "changeme",
            "secret",
            "your-secret-key",
            "replace_with_long_random_string_min_32_chars",
        }
        if v.lower() in weak_values:
            raise ValueError("JWT_SECRET_KEY appears to be a placeholder — set a real secret")
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    @lru_cache ensures we read .env only once per process.
    Used as a FastAPI dependency: `settings: Settings = Depends(get_settings)`.
    """
    return Settings()


# Convenience singleton (for use outside FastAPI DI, e.g., scripts)
settings = get_settings()
