#!/bin/bash
# Build script for Vercel Deployment

echo "=== Installing dependencies ==="
python3 -m pip install -r requirements/base.txt

echo "=== Collecting Static Files ==="
python3 manage.py collectstatic --noinput --clear

echo "=== Build Complete ==="
