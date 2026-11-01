"""Create a private local configuration without printing credentials."""

import json
import os
import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    credentials = {
        "SECRET_KEY": secrets.token_urlsafe(64),
        "INGEST_API_TOKENS": "'" + json.dumps({"local-ingestor": secrets.token_urlsafe(48)}) + "'",
        "DATABASE_PASSWORD": secrets.token_urlsafe(32),
        "POSTGRES_ADMIN_PASSWORD": secrets.token_urlsafe(48),
        "MIGRATION_DATABASE_PASSWORD": secrets.token_urlsafe(32),
        "REDIS_PASSWORD": secrets.token_urlsafe(32),
    }
    credentials["REDIS_URL"] = f"redis://:{credentials['REDIS_PASSWORD']}@redis:6379/1"
    template = (root / ".env.example").read_text(encoding="utf-8")
    lines = []
    for line in template.splitlines():
        key, separator, _ = line.partition("=")
        lines.append(f"{key}={credentials[key]}" if separator and key in credentials else line)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
    except FileExistsError:
        raise SystemExit(".env already exists; it was preserved.") from None
    print("Created .env with private random credentials. No credentials were printed.")


if __name__ == "__main__":
    main()
