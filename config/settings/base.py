"""Shared application configuration; choose development, test, or production explicitly."""

import json
import os
from pathlib import Path
from typing import Any, cast

import structlog
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def env_int(name: str, default: int, *, maximum: int = 1_000_000) -> int:
    """Read bounded positive integers so invalid operational limits fail at startup."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from exc
    if not 1 <= value <= maximum:
        raise ImproperlyConfigured(f"{name} must be between 1 and {maximum}")
    return value


def env_bool(name: str, default: bool) -> bool:
    """Require explicit boolean values instead of silently weakening security on typos."""
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false"}:
        raise ImproperlyConfigured(f"{name} must be true or false")
    return value == "true"


def parse_ingest_tokens(value: str) -> dict[str, str]:
    """Parse named service credentials without including secret values in errors."""
    try:
        parsed: object = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ImproperlyConfigured("INGEST_API_TOKENS must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ImproperlyConfigured("INGEST_API_TOKENS must be a JSON object")
    tokens: dict[str, str] = {}
    for name, token in cast(dict[object, object], parsed).items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ImproperlyConfigured("INGEST_API_TOKENS requires nonempty client names up to 100 characters")
        if not isinstance(token, str) or not token or len(token) > 1024:
            raise ImproperlyConfigured("INGEST_API_TOKENS requires nonempty string credentials up to 1024 characters")
        if not token.isascii() or any(character.isspace() for character in token):
            raise ImproperlyConfigured("INGEST_API_TOKENS credentials must use ASCII without whitespace")
        tokens[name] = token
    if len(set(tokens.values())) != len(tokens):
        raise ImproperlyConfigured("INGEST_API_TOKENS credentials must be unique per client")
    return tokens


SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS: list[str] = []
INGEST_API_TOKENS = parse_ingest_tokens(os.getenv("INGEST_API_TOKENS", "{}"))
INGEST_RATE_LIMIT = env_int("INGEST_RATE_LIMIT", 300)
INGEST_RATE_WINDOW_SECONDS = env_int("INGEST_RATE_WINDOW_SECONDS", 60, maximum=86_400)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "trades",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME", "novatrade"),
        "USER": os.getenv("DATABASE_USER", "nova"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", ""),
        "HOST": os.getenv("DATABASE_HOST", "postgres"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
        "OPTIONS": {"connect_timeout": 10},
        # Django's async ORM uses sync adapters; persistent connections are disabled for ASGI.
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "novatradecore"}}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
