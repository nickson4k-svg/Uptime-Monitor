# ADR 0002: Multi-Region Probing & Quorum Consensus ($N$ of $M$ Rule)

## Status
Accepted

## Context
Single-point monitoring probes are vulnerable to transient network blips, regional ISP throttling, and BGP routing hiccups. Triggering incident alerts on a single regional failure produces false-positive alarm fatigue for operations teams.

## Decision
We implemented distributed multi-region probing with configurable **Quorum Consensus**:
1. Monitors declare configured regions: `eu-central` (Frankfurt), `us-east` (N. Virginia), `ap-southeast` (Singapore) and a `quorum_threshold` ($1 \le K \le M$).
2. Celery Beat executes a parallel fan-out across all configured regions.
3. The `IncidentService` evaluates state using quorum consensus:
   - An incident is **opened** only when $\text{failing\_regions} \ge \text{quorum\_threshold}$.
   - If fewer regions fail, the failure is logged and recorded in telemetry, but incident escalation is suppressed.
   - When healthy regions recover such that active failures $< \text{quorum\_threshold}$, the incident is automatically resolved.
4. Incident root cause messages automatically format consensus telemetry (e.g. `Outage confirmed by 2/3 regions (eu-central, us-east): ...`).

## Consequences
### Positive
- Drastically reduces false alerts caused by localized cloud networking disruptions.
- Users gain granular visibility into regional availability across global geographies.
- Catalyst UI cleanly renders regional badges and latency breakdowns.

### Trade-offs
- Celery check volume scales linearly with the number of selected regions ($M \times \text{monitors}$).
