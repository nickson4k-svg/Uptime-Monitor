#!/bin/bash
set -e

# Build script for Vercel Deployment

echo "=== Setting up Python environment ==="
export PIP_BREAK_SYSTEM_PACKAGES=1

if command -v uv &> /dev/null; then
    echo "Found uv: creating Python 3.11 virtual environment..."
    uv venv --python 3.11 .build-venv
    # shellcheck disable=SC1091
    source .build-venv/bin/activate
    echo "Installing requirements with uv pip..."
    uv pip install -r requirements.txt
    PYTHON_CMD="python"
elif command -v python3.11 &> /dev/null; then
    echo "Using python3.11..."
    python3.11 -m pip install --break-system-packages -r requirements.txt
    PYTHON_CMD="python3.11"
elif command -v python3.12 &> /dev/null; then
    echo "Using python3.12..."
    python3.12 -m pip install --break-system-packages -r requirements.txt
    PYTHON_CMD="python3.12"
else
    echo "Using system python3..."
    python3 -m pip install --break-system-packages -r requirements.txt
    PYTHON_CMD="python3"
fi

echo "=== Collecting Static Files ==="
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY="${SECRET_KEY:-django-insecure-build-placeholder-key-for-collectstatic}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-.vercel.app,localhost,127.0.0.1}"

$PYTHON_CMD manage.py collectstatic --noinput --clear

echo "=== Build Complete ==="


