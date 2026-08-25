# ADR 0005: Hybrid ASGI / Serverless Vercel Deployment Architecture

## Status
Accepted

## Context
Deploying Django applications with real-time WebSockets and Celery background workers across heterogeneous hosting targets (e.g. Serverless Vercel, Docker Compose, or Cloud Kubernetes) requires clean separation of WSGI HTTP handlers, ASGI WebSocket channels, and async background workers.

## Decision
We established a hybrid multi-mode execution topology:
1. **Serverless Deployment (Vercel)**:
   - Configured `vercel.json` with `@vercel/python` targeting `config/wsgi.py` (`app = application`).
   - `build_files.sh` handles automated dependency installation and static asset minification (`collectstatic`).
2. **Containerized / Cloud Deployment (Docker Compose / Kubernetes)**:
   - `web`: Daphne ASGI server handling simultaneous HTTP and WebSocket traffic on port 8000.
   - `worker-checks`: Dedicated Celery worker pool executing probe strategies.
   - `worker-notifications`: Dedicated Celery worker handling alert delivery.
   - `beat`: Celery Beat master scheduler orchestrating periodic fan-outs.
   - `redis`: Shared Broker and Channels layer.

## Consequences
### Positive
- Zero code duplication between serverless and containerized deployment modes.
- Instant 1-click cloud previews on Vercel while preserving real-time WebSocket capabilities in containerized environments.
