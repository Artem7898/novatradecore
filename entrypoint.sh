#!/bin/sh

set -e

echo "⏳ Waiting for PostgreSQL..."

until pg_isready -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER"; do
  sleep 2
done

echo "✅ PostgreSQL is ready"

echo "🚀 Applying migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static..."
python manage.py collectstatic --noinput || true

echo "🔥 Starting app..."
exec "$@"