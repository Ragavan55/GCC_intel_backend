from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parents[1]
REQUIRED_KEYS = {"SECRET_KEY", "DATABASE_URL"}
OPTIONAL_KEYS = {
    "APP_ENV", "APP_NAME", "API_PREFIX", "HOST", "PORT", "FRONTEND_ORIGIN",
    "JWT_ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES",
    "COOKIE_SECURE", "COOKIE_SAMESITE", "ADMIN_EMAIL", "AI_BASE_URL", "GROQ_API_KEY", "AI_MODEL",
    "AI_MAX_TOOL_ROUNDS", "AI_TEMPERATURE", "CHAT_RATE_LIMIT_PER_MINUTE", "LOG_LEVEL",
    "LOG_DIR", "LOG_FILE", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT", "LOG_RETENTION_DAYS",
}


def main() -> int:
    env_path = BACKEND_DIR / ".env"
    values = dotenv_values(env_path) if env_path.exists() else {}
    print(f"Environment file: {env_path}")
    print(f"{'VARIABLE':<36} {'STATUS':<10} REQUIREMENT")
    print("-" * 64)
    missing_required = False
    for name in sorted(REQUIRED_KEYS | OPTIONAL_KEYS):
        value = os.environ.get(name, values.get(name))
        is_set = value is not None and str(value).strip() != ""
        requirement = "REQUIRED" if name in REQUIRED_KEYS else "OPTIONAL"
        print(f"{name:<36} {'SET' if is_set else 'MISSING':<10} {requirement}")
        if name in REQUIRED_KEYS and not is_set:
            missing_required = True
    return 1 if missing_required else 0


if __name__ == "__main__":
    raise SystemExit(main())
