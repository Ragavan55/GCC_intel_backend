from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "GCC Intelligence India"
    api_prefix: str = "/api"
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    database_url: str = "sqlite:///./gcc.db"
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    admin_email: str = ""

    ai_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: str = ""
    ai_model: str = "openai/gpt-oss-120b"
    ai_max_tool_rounds: int = 4
    ai_temperature: float = 0
    chat_rate_limit_per_minute: int = 10

    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_file: str = "app.log"
    log_max_bytes: int = 5_242_880
    log_backup_count: int = 5
    log_retention_days: int = 30

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def absolute_log_dir(self) -> Path:
        path = Path(self.log_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def effective_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url

    @property
    def effective_ai_api_key(self) -> str:
        raw_key = self.groq_api_key or os.getenv("GROQ_API_KEY", "")
        return raw_key.strip().strip('"').strip("'")

    @property
    def effective_ai_model(self) -> str:
        return self.ai_model.strip().strip('"').strip("'") or "openai/gpt-oss-120b"

    @property
    def groq_chat_completions_url(self) -> str:
        base_url = self.ai_base_url.strip().strip('"').strip("'").rstrip("/")
        return f"{base_url}/chat/completions"

    def validate_startup(self) -> None:
        missing_hard_requirements = [
            name
            for name, value in (
                ("SECRET_KEY", self.secret_key),
                ("DATABASE_URL", self.database_url),
            )
            if not value.strip()
        ]
        missing_setup_values = [
            name
            for name, value in (
                ("ADMIN_EMAIL", self.admin_email),
                ("GROQ_API_KEY", self.effective_ai_api_key),
                ("AI_MODEL", self.effective_ai_model),
            )
            if not value.strip()
        ]
        if missing_hard_requirements or missing_setup_values:
            logging.getLogger(__name__).warning(
                "Missing environment configuration: %s",
                ", ".join(missing_hard_requirements + missing_setup_values),
            )
        if missing_hard_requirements:
            raise RuntimeError(
                "Missing required environment configuration: "
                + ", ".join(missing_hard_requirements)
            )
        if not self.effective_ai_api_key or not self.effective_ai_model:
            logging.getLogger(__name__).warning(
                "AI chat will use database-only answers until GROQ_API_KEY and AI_MODEL are configured."
            )


settings = Settings()
