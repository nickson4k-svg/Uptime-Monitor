# ADR 0004: Observability, Prometheus Metrics & Zero-Downtime Health Probes

## Status
Accepted

## Context
Production Kubernetes deployments and cloud orchestrators require standard health signals for liveness, readiness, traffic routing, and cluster auto-scaling. Additionally, centralized logging and Prometheus scraping are essential for enterprise SRE operations.

## Decision
We implemented comprehensive observability infrastructure:
1. **Kubernetes Health Probes**:
   - `GET /health/live/`: Fast, lightweight process liveness check ($O(1)$).
   - `GET /health/ready/`: Deep subsystem readiness check verifying PostgreSQL connection, Redis channel layer ping, and database read/write readiness.
2. **Prometheus Metrics Exporter**:
   - `GET /metrics`: Standard OpenMetrics/Prometheus scraper exposing:
     - `uptime_checks_total` (counter partitioned by status and region)
     - `uptime_check_duration_seconds` (histogram with latency buckets)
     - `uptime_active_incidents` (gauge of open incidents)
     - `uptime_monitors_total` (gauge partitioned by status and active state)
3. **Structured JSON Logging & Correlation IDs**:
   - `RequestIDMiddleware` generates or propagates `X-Request-ID` across every incoming request and downstream log entry.
   - `StructuredJSONFormatter` emits machine-readable JSON logs for Vector/Datadog/Grafana Loki ingestion.

## Consequences
### Positive
- Fully compatible with cloud-native monitoring (Prometheus, Grafana, Datadog).
- Zero-downtime rolling deployments via Kubernetes readiness gating.
- Fast root cause tracing via distributed request IDs.
