"""Service authentication and shared fixed-window admission control for ingestion."""

import hashlib
import secrets
from asyncio import to_thread
from collections.abc import Mapping
from time import time
from typing import cast

import structlog
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

logger = structlog.get_logger(__name__)


def _unauthorized() -> JsonResponse:
    response = JsonResponse({"error": "Unauthorized"}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    return response


def _increment_counter(cache_key: str, timeout: int) -> int:
    """Use backend atomic operations; BaseCache.aincr() is a non-atomic get/set."""
    if cache.add(cache_key, 1, timeout=timeout):
        return 1
    return cache.incr(cache_key)


async def authorize_ingest(request: HttpRequest) -> JsonResponse | None:
    """Authenticate a service and enforce its shared limit, failing closed on cache errors."""
    scheme, separator, credential = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not credential or len(credential) > 1024:
        return _unauthorized()
    principal: str | None = None
    configured_tokens = cast(Mapping[str, str], settings.INGEST_API_TOKENS)
    # Check every configured key so key order does not reveal which service matched.
    for client_name, expected in configured_tokens.items():
        if secrets.compare_digest(credential.encode("utf-8"), expected.encode("utf-8")):
            principal = client_name
    if principal is None:
        return _unauthorized()

    window_seconds = cast(int, settings.INGEST_RATE_WINDOW_SECONDS)
    limit = cast(int, settings.INGEST_RATE_LIMIT)
    timestamp = int(time())
    window = timestamp // window_seconds
    retry_after = max(1, window_seconds - timestamp % window_seconds)
    principal_hash = hashlib.sha256(principal.encode("utf-8")).hexdigest()
    cache_key = f"ingest-rate:{principal_hash}:{window}"
    try:
        count = await to_thread(_increment_counter, cache_key, window_seconds + 1)
    except Exception as exc:
        # Exception messages can include Redis credentials; retain only the failure category.
        logger.error("ingest_rate_limit_unavailable", error_type=type(exc).__name__)
        response = JsonResponse({"error": "Admission control unavailable"}, status=503)
        response["Retry-After"] = "1"
        return response
    if count > limit:
        response = JsonResponse({"error": "Rate limit exceeded"}, status=429)
        response["Retry-After"] = str(retry_after)
        return response
    return None
