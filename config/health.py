"""Minimal health endpoints without diagnostic data leakage."""

from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET
from redis.exceptions import RedisError


@require_GET
async def live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def _database_ready() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


@require_GET
async def ready(request: HttpRequest) -> JsonResponse:
    try:
        await sync_to_async(_database_ready, thread_sensitive=True)()
        await cache.aget("novatradecore:readiness")
    except (DatabaseError, RedisError, OSError, RuntimeError):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
