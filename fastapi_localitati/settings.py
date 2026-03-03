"""
Centralized application settings using pydantic-settings.

Loads configuration from environment variables with sane defaults for development.
In production (ENV=prod), some settings must be explicitly provided and validated.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field

# Optional dependency: pydantic-settings. Provide a fallback if not installed.
try:
    from pydantic_settings import BaseSettings  # type: ignore

    _HAS_PYDANTIC_SETTINGS = True
except Exception:  # pragma: no cover - fallback path
    BaseSettings = object  # type: ignore
    _HAS_PYDANTIC_SETTINGS = False


class Settings(BaseSettings):
    # Environment: dev/test/prod controls some safety checks
    ENV: Literal["dev", "test", "prod"] = "dev"

    # Security / auth
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-change-me",
        description="Secret key used to sign JWTs. Must be long and random in production.",
        min_length=16,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Admin seeding (dev convenience)
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    SEED_ADMIN_ON_STARTUP: bool = False

    # Database (optional override; primary source may be in database module)
    DATABASE_URL: str | None = None

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    CORS_ALLOW_HEADERS: List[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type"]
    )

    # Rate limiting (very basic in-memory hook)
    RATE_LIMIT_PER_MINUTE: int = 120

    # Logging
    LOG_LEVEL: str = "INFO"

    # Only respected when using pydantic-settings; harmless otherwise
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def ensure_prod_safety(self) -> None:
        if self.ENV == "prod":
            # Very naive checks, just to avoid footguns
            if (
                not self.SECRET_KEY
                or self.SECRET_KEY == "dev-insecure-secret-change-me"
            ):
                raise ValueError(
                    "SECRET_KEY must be set to a strong value in production (ENV=prod)"
                )
            if not self.DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL must be configured in production (ENV=prod)"
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if _HAS_PYDANTIC_SETTINGS:
        s = Settings()  # type: ignore[call-arg]
    else:
        # Fallback: manually construct from environment without validation
        import os, json

        def _get_bool(name: str, default: bool) -> bool:
            return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

        def _get_int(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except ValueError:
                return default

        def _get_list(name: str, default: List[str]) -> List[str]:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                val = json.loads(raw)
                if isinstance(val, list):
                    return [str(x) for x in val]
            except Exception:
                pass
            # comma-separated fallback
            return [x.strip() for x in raw.split(",") if x.strip()]

        from pydantic import BaseModel

        class FallbackSettings(BaseModel):
            ENV: Literal["dev", "test", "prod"] = os.getenv("ENV", "dev")
            SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
            ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
            ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int(
                "ACCESS_TOKEN_EXPIRE_MINUTES", 30
            )
            REFRESH_TOKEN_EXPIRE_DAYS: int = _get_int("REFRESH_TOKEN_EXPIRE_DAYS", 7)
            ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
            ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
            SEED_ADMIN_ON_STARTUP: bool = _get_bool("SEED_ADMIN_ON_STARTUP", False)
            DATABASE_URL: str | None = os.getenv("DATABASE_URL")
            CORS_ORIGINS: List[str] = _get_list(
                "CORS_ORIGINS",
                [
                    "http://localhost",
                    "http://localhost:3000",
                    "http://localhost:8080",
                    "http://127.0.0.1",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8080",
                ],
            )
            CORS_ALLOW_CREDENTIALS: bool = _get_bool("CORS_ALLOW_CREDENTIALS", True)
            CORS_ALLOW_METHODS: List[str] = _get_list(
                "CORS_ALLOW_METHODS", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
            )
            CORS_ALLOW_HEADERS: List[str] = _get_list(
                "CORS_ALLOW_HEADERS", ["Authorization", "Content-Type"]
            )
            RATE_LIMIT_PER_MINUTE: int = _get_int("RATE_LIMIT_PER_MINUTE", 120)
            LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

            def ensure_prod_safety(self) -> None:
                if self.ENV == "prod":
                    if (
                        not self.SECRET_KEY
                        or self.SECRET_KEY == "dev-insecure-secret-change-me"
                    ):
                        raise ValueError(
                            "SECRET_KEY must be set to a strong value in production (ENV=prod)"
                        )
                    if not self.DATABASE_URL:
                        raise ValueError(
                            "DATABASE_URL must be configured in production (ENV=prod)"
                        )

        s = FallbackSettings()  # type: ignore[assignment]
    s.ensure_prod_safety()  # type: ignore[attr-defined]
    return s  # type: ignore[return-value]
