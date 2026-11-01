"""Fail-closed production settings for a deployment behind a trusted TLS ingress."""

# pyright: reportConstantRedefinition=false

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from . import base
from .base import *  # noqa: F403


def _required(name: str) -> str:
    value = os.getenv(name, "")
    if not value.strip():
        raise ImproperlyConfigured(f"{name} is required in production")
    return value


def _is_placeholder(value: str) -> bool:
    return value.lower().startswith(("django-insecure-", "replace-", "change-me", "test-token", "development-"))


DEBUG = False
SECRET_KEY = _required("SECRET_KEY")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 10 or _is_placeholder(SECRET_KEY):
    raise ImproperlyConfigured("SECRET_KEY must be a unique generated production secret of at least 50 characters")
ALLOWED_HOSTS = [host.strip() for host in _required("ALLOWED_HOSTS").split(",") if host.strip()]
if not ALLOWED_HOSTS or any("*" in host or "://" in host or "/" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("ALLOWED_HOSTS must contain explicit hosts without wildcards or URL schemes")
INGEST_API_TOKENS = base.parse_ingest_tokens(_required("INGEST_API_TOKENS"))
if not INGEST_API_TOKENS or any(len(token) < 32 or _is_placeholder(token) for token in INGEST_API_TOKENS.values()):
    raise ImproperlyConfigured("INGEST_API_TOKENS requires generated production credentials of at least 32 characters")
_database_password = _required("DATABASE_PASSWORD")
if len(_database_password) < 32 or _is_placeholder(_database_password):
    raise ImproperlyConfigured("DATABASE_PASSWORD must be a generated production credential of at least 32 characters")
DATABASES = {"default": {**base.DATABASES["default"], "PASSWORD": _database_password}}
REDIS_URL = _required("REDIS_URL")
try:
    _redis_location = urlsplit(REDIS_URL)
except ValueError as exc:
    raise ImproperlyConfigured("REDIS_URL must be a redis:// or rediss:// URL") from exc
if _redis_location.scheme not in {"redis", "rediss"} or not _redis_location.hostname:
    raise ImproperlyConfigured("REDIS_URL must be a redis:// or rediss:// URL")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "novatradecore",
        "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
    }
}
SECURE_SSL_REDIRECT = base.env_bool("SECURE_SSL_REDIRECT", True)
# The liveness endpoint carries no user data and is used by the container's HTTP probe.
SECURE_REDIRECT_EXEMPT = [r"^health/live/$", r"^health/ready/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = base.env_int("SECURE_HSTS_SECONDS", 3600, maximum=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
# Enable only when the deployment restricts access to an ingress that overwrites this header.
if base.env_bool("TRUST_PROXY_HEADERS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
