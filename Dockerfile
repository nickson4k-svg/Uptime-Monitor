# ─── Stage 1: Build dependencies ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps for psycopg and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt

RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements/production.txt

# ─── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appgroup /app/staticfiles /app/media

USER appuser

EXPOSE 8000

# Default: run Daphne (ASGI) for web container
# Override CMD in docker-compose for worker/beat
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]

# ─── Stage 3: Development image ───────────────────────────────────────────────
FROM python:3.12-slim AS development

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=config.settings.local

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/local.txt requirements/local.txt
COPY requirements/base.txt requirements/base.txt

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements/local.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
