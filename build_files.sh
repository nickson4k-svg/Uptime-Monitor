#!/bin/bash
set -e

# Build script for Vercel Deployment

echo "=== Ensuring staticfiles directory exists ==="
mkdir -p staticfiles

echo "=== Collecting Static Files ==="
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY="${SECRET_KEY:-django-insecure-build-placeholder-key-for-collectstatic}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-.vercel.app,localhost,127.0.0.1}"

if command -v uv &> /dev/null; then
    echo "Attempting static collection via uv..."
    (uv venv --python 3.12 .build-venv 2>/dev/null || uv venv .build-venv) && \
    # shellcheck disable=SC1091
    source .build-venv/bin/activate && \
    uv pip install -r requirements.txt && \
    python manage.py collectstatic --noinput --clear || echo "Using pre-collected static files from repository."
elif command -v python3 &> /dev/null; then
    python3 manage.py collectstatic --noinput --clear || echo "Using pre-collected static files from repository."
fi

# Ensure staticfiles is present
mkdir -p staticfiles

echo "=== Build Complete ==="
