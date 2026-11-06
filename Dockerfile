# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12.15-slim-bookworm AS builder

ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_NO_CACHE=1
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Optional build secrets support proxies with a private CA; standard builds use OS trust.
RUN --mount=type=secret,id=proxy_ca --mount=type=secret,id=system_ca \
    if [ -f /run/secrets/system_ca ]; then export SSL_CERT_FILE=/run/secrets/system_ca; \
    elif [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY README.md README_EN.md manage.py ./
COPY config ./config
COPY trades ./trades
RUN --mount=type=secret,id=proxy_ca --mount=type=secret,id=system_ca \
    if [ -f /run/secrets/system_ca ]; then export SSL_CERT_FILE=/run/secrets/system_ca; \
    elif [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-editable

FROM python:3.12.15-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production
WORKDIR /app
RUN groupadd --gid 10001 nova && useradd --uid 10001 --gid nova --no-create-home nova \
    && mkdir -p /app/staticfiles && chown nova:nova /app/staticfiles
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/manage.py /app/manage.py
COPY --from=builder /app/config /app/config
COPY --from=builder /app/trades /app/trades
COPY scripts/wait_for_database.py /app/scripts/wait_for_database.py
COPY scripts/check_health.py /app/scripts/check_health.py
COPY --chmod=755 entrypoint.sh /entrypoint.sh
RUN chmod -R a+rX /app/config /app/trades /app/scripts && chmod a+r /app/manage.py
USER nova
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "/app/scripts/check_health.py"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
