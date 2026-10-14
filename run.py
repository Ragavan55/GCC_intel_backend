from __future__ import annotations

import os

import uvicorn

from app.config import settings


def main() -> None:
    port = int(os.environ.get("PORT", str(settings.port)))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()