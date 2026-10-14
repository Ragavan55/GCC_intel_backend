from __future__ import annotations

import secrets
from pathlib import Path


def main() -> None:
    # Equivalent manual command: python -c "import secrets; print(secrets.token_hex(32))"
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        raise SystemExit(f"Missing {env_path}; copy .env.example to .env first.")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    replacement = f"SECRET_KEY={secrets.token_hex(32)}"
    for index, line in enumerate(lines):
        if line.startswith("SECRET_KEY="):
            lines[index] = replacement
            break
    else:
        lines.extend(["", replacement])
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated SECRET_KEY in {env_path}; value not displayed.")


if __name__ == "__main__":
    main()
