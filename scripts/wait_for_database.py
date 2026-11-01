"""Bound database startup waits without exposing connection credentials."""

import os
import time

import psycopg
from django.conf import settings


def main() -> None:
    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.postgresql":
        return
    timeout = int(os.getenv("DATABASE_WAIT_TIMEOUT", "60"))
    if not 1 <= timeout <= 300:
        raise SystemExit("DATABASE_WAIT_TIMEOUT must be between 1 and 300 seconds.")
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SystemExit("Database did not become ready within DATABASE_WAIT_TIMEOUT.")
        try:
            with psycopg.connect(
                dbname=database["NAME"],
                user=database["USER"],
                password=database["PASSWORD"],
                host=database["HOST"],
                port=database["PORT"],
                connect_timeout=max(1, min(3, int(remaining))),
            ):
                print("Database connection is ready.", flush=True)
                return
        except psycopg.OperationalError:
            time.sleep(min(1, max(0, deadline - time.monotonic())))


if __name__ == "__main__":
    main()
