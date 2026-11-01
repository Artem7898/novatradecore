"""Deterministic tests; set TEST_DATABASE_ENGINE=postgresql for integration parity."""

# pyright: reportConstantRedefinition=false

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

# This deterministic key is restricted to test settings.
SECRET_KEY = "test-only-secret-for-novatradecore-tests-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # nosec B105
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
INGEST_API_TOKENS = {"test-client": "test-token-for-novatradecore-tests-0123456789"}
INGEST_RATE_LIMIT = 300
INGEST_RATE_WINDOW_SECONDS = 60
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "novatradecore-tests"}}
_database_engine = os.getenv("TEST_DATABASE_ENGINE", "sqlite")
if _database_engine == "sqlite":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
elif _database_engine != "postgresql":
    raise ImproperlyConfigured("TEST_DATABASE_ENGINE must be sqlite or postgresql")
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
