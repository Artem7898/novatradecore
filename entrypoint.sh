#!/bin/sh
set -eu

if [ "${WAIT_FOR_DATABASE:-1}" = "1" ]; then
    python /app/scripts/wait_for_database.py
fi

# Migrations and collectstatic are explicit release steps (make release).
exec "$@"
