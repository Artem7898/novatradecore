"""Deployment settings must reject missing credentials and unsafe defaults."""

import json
import runpy

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import parse_ingest_tokens


@pytest.fixture
def production_environment(monkeypatch):
    values = {
        "SECRET_KEY": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-generated-secret",
        "ALLOWED_HOSTS": "trades.example.org",
        "INGEST_API_TOKENS": json.dumps({"ingestor": "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"}),
        "DATABASE_PASSWORD": "generated-database-credential-for-settings-tests",
        "REDIS_URL": "redis://redis.internal:6379/1",
        "TRUST_PROXY_HEADERS": "false",
        "SECURE_SSL_REDIRECT": "true",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


@pytest.mark.parametrize(
    "missing", ["SECRET_KEY", "ALLOWED_HOSTS", "INGEST_API_TOKENS", "DATABASE_PASSWORD", "REDIS_URL"]
)
def test_production_requires_explicit_credentials_and_hosts(production_environment, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(ImproperlyConfigured, match=missing):
        runpy.run_module("config.settings.production")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SECRET_KEY", "short"),
        ("SECRET_KEY", "django-insecure-" + "aB0123456789" * 6),
        ("ALLOWED_HOSTS", "*"),
        ("ALLOWED_HOSTS", "https://trades.example.org"),
        ("INGEST_API_TOKENS", "{}"),
        ("INGEST_API_TOKENS", json.dumps({"client": "short"})),
        ("INGEST_API_TOKENS", json.dumps({"client": "test-token-not-valid-in-production-0123456789"})),
        ("DATABASE_PASSWORD", "nova_pass"),
        ("DATABASE_PASSWORD", "a-short-nondefault-password"),
        ("REDIS_URL", "https://redis.internal"),
        ("SECURE_SSL_REDIRECT", "typo"),
        ("TRUST_PROXY_HEADERS", "typo"),
    ],
)
def test_production_rejects_unsafe_configuration(production_environment, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ImproperlyConfigured, match=name):
        runpy.run_module("config.settings.production")


def test_production_enables_security_and_shared_rate_limiting(production_environment):
    configured = runpy.run_module("config.settings.production")
    assert configured["DEBUG"] is False
    assert configured["DATABASES"]["default"]["CONN_MAX_AGE"] == 0
    assert configured["CACHES"]["default"]["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    assert configured["SESSION_COOKIE_SECURE"] is True
    assert configured["CSRF_COOKIE_SECURE"] is True
    assert configured["SECURE_SSL_REDIRECT"] is True
    assert "SECURE_PROXY_SSL_HEADER" not in configured
    assert "django.middleware.clickjacking.XFrameOptionsMiddleware" in configured["MIDDLEWARE"]


def test_forwarded_scheme_is_trusted_only_with_explicit_opt_in(production_environment, monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    configured = runpy.run_module("config.settings.production")
    assert configured["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")


@pytest.mark.parametrize(
    "value",
    [
        "[]",
        "null",
        "not-json",
        '{"client":123}',
        '{"": "credential"}',
        '{"client": "has whitespace"}',
        '{"one": "same", "two": "same"}',
    ],
)
def test_token_configuration_rejects_ambiguous_or_malformed_values(value):
    with pytest.raises(ImproperlyConfigured, match="INGEST_API_TOKENS"):
        parse_ingest_tokens(value)
