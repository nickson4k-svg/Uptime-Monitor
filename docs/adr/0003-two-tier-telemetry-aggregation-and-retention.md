# ADR 0003: Two-Tier Telemetry Aggregation & Chunked Retention Pruning

## Status
Accepted

## Context
High-frequency uptime monitoring generates millions of `CheckResult` rows per week. Computing 24-hour, 7-day, and 30-day uptime percentages dynamically on dashboard page-loads would cause severe disk I/O bottlenecks and database locking on large tables.

## Decision
We implemented a two-tier time-series roll-up architecture:
1. **Tier 1 (Hourly Rollup)**: Celery periodic task `aggregate_hourly_stats` runs every hour, compressing 60 raw checks into a single `HourlyStats` record with precomputed `total_checks`, `up_checks`, `avg_response_time_ms`, and `uptime_pct`.
2. **Tier 2 (Daily Rollup)**: Celery task `aggregate_daily_stats` summarizes 24 `HourlyStats` rows into one `DailyStats` record per monitor.
3. **Chunked Retention Pruning**: Periodic task `prune_old_checks(days=30, batch_size=5000)` deletes raw `CheckResult` records older than 30 days in non-blocking batches.
4. **ORM Subquery Optimization**: `MonitorViewSet.get_queryset()` annotates the 24h uptime metric directly onto the `Monitor` queryset using a SQL `Subquery`, eliminating N+1 queries.

## Consequences
### Positive
- Dashboard queries read exactly $O(24)$ or $O(30)$ rows instead of scanning millions of records.
- Database table size remains bounded and predictable.
- Eliminates N+1 query overhead in DRF serialization.

### Trade-offs
- Telemetry resolution beyond 30 days is preserved at daily granularity rather than sub-minute granularity.
