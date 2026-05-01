# ==========================================
# ЭТАП 1: Builder
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN pip install --no-cache-dir --extra-index-url https://test.pypi.org/simple/ .

# ==========================================
# ЭТАП 2: Runner
# ==========================================
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 👇 сначала пользователь
RUN groupadd -r nova && useradd -r -g nova nova

# 👇 потом директории
RUN mkdir -p /app/staticfiles && chown -R nova:nova /app

# 👇 копируем зависимости из builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 👇 копируем код
COPY --chown=nova:nova . /app

COPY --chown=nova:nova entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER nova

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]