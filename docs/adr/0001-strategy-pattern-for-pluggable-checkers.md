# ADR 0001: Strategy Pattern for Pluggable Monitor Checkers

## Status
Accepted

## Context
The initial monitoring engine was hard-coded specifically for HTTP `GET`/`POST` requests. As requirements expanded to support diverse infrastructure components (TLS certificates, TCP services, DNS root domains, DOM keyword searches), embedding protocol-specific logic directly into the Celery task violated the Open-Closed Principle (OCP) and Single Responsibility Principle (SRP).

## Decision
We implemented the **Strategy Pattern** with a centralized **Factory**:
1. Defined `BaseChecker(ABC)` in `checks/checkers/base.py` enforcing the `check(monitor, region) -> CheckResultData` interface.
2. Created concrete strategies:
   - `HttpChecker`: Protocol status codes and latency.
   - `KeywordChecker`: HTML DOM payload substring assertions.
   - `SSLCertChecker`: TLS handshake, certificate chain validation, and expiration threshold evaluation.
   - `TCPChecker`: Socket connect probe with millisecond latency measurement.
   - `DomainExpiryChecker`: WHOIS RDAP expiration querying.
3. Created `CheckerFactory` in `checks/checkers/factory.py` to decouple task execution from specific protocol checkers.

## Consequences
### Positive
- Adding a new protocol (e.g. gRPC, ICMP Ping, DNS Record) requires only creating a new checker class and registering it in the factory without touching task orchestration or incident management.
- Unit testing is completely isolated and fast using mock sockets/HTTP transports.
- Extensible metadata payload stored in `CheckResult.metadata` JSONField.

### Trade-offs
- Slight increase in class count and abstractions compared to procedural script execution.
