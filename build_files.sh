#!/bin/bash
set -e

# Build script for Vercel Deployment

echo "=== Installing dependencies ==="
export PIP_BREAK_SYSTEM_PACKAGES=1

if command -v uv &> /dev/null; then
    echo "Found uv: installing dependencies via uv pip..."
    uv pip install --system -r requirements.txt
else
    echo "Using pip with --break-system-packages..."
    python3 -m pip install --break-system-packages -r requirements.txt
fi

echo "=== Collecting Static Files ==="
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY="${SECRET_KEY:-django-insecure-build-placeholder-key-for-collectstatic}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-.vercel.app,localhost,127.0.0.1}"

python3 manage.py collectstatic --noinput --clear

echo "=== Build Complete ==="

