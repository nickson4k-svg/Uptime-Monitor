"""
DomainExpiryChecker — Strategy implementation for domain registration validity and expiration monitoring.

Design:
- Uses RDAP (Registration Data Access Protocol - RFC 7484 / ICANN standard).
- Queries domain registry to extract authoritative expiration timestamp.
- Triggers alert if domain registration expires within domain_threshold_days.
"""

import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from checks.checkers.base import BaseChecker, CheckResultData
from checks.models import CheckErrorType, CheckStatus


class DomainExpiryChecker(BaseChecker):
    """
    Checks domain expiration via RDAP (Registration Data Access Protocol).
    """

    def __init__(self, monitor_data) -> None:
        super().__init__(monitor_data)
        self.threshold_days = int(monitor_data.get("domain_threshold_days") or 30)

    def _extract_domain(self) -> str:
        target = self.url.strip()
        if target.startswith(("http://", "https://")):
            parsed = urlparse(target)
            domain = parsed.hostname or target
        else:
            domain = target.split("/")[0].split(":")[0]
        return domain.lower()

    def _execute(self, start_time: float) -> CheckResultData:
        domain = self._extract_domain()
        timeout = float(self.timeout)

        # Standard RDAP gateway
        rdap_url = f"https://rdap.org/domain/{domain}"

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(
                    rdap_url,
                    headers={
                        "Accept": "application/rdap+json, application/json",
                        "User-Agent": "PetUptimeMonitor/1.0",
                    },
                )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if resp.status_code == 404:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=404,
                    error_type=CheckErrorType.DOMAIN_EXPIRED,
                    error_message=f"Domain '{domain}' is not registered or not found in RDAP registry.",
                )

            if not resp.is_success:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=resp.status_code,
                    error_type=CheckErrorType.CONNECTION_ERROR,
                    error_message=f"RDAP registry returned status {resp.status_code} for domain '{domain}'.",
                )

            data = resp.json()
            events = data.get("events", [])
            expiration_date_str = None

            for event in events:
                if event.get("eventAction") == "expiration":
                    expiration_date_str = event.get("eventDate")
                    break

            if not expiration_date_str:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.UNKNOWN,
                    error_message=f"Could not extract expiration date from RDAP response for domain '{domain}'.",
                )

            # Format e.g. 2027-05-15T00:00:00Z
            clean_date_str = expiration_date_str.replace("Z", "+00:00")
            expire_date = datetime.fromisoformat(clean_date_str)
            now = datetime.now(UTC)

            days_left = (expire_date - now).days

            if days_left < 0:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.DOMAIN_EXPIRED,
                    error_message=f"Domain '{domain}' expired {abs(days_left)} days ago ({expire_date.strftime('%Y-%m-%d')}).",
                )
            elif days_left <= self.threshold_days:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.DOMAIN_EXPIRING_SOON,
                    error_message=f"Domain '{domain}' expires in {days_left} days ({expire_date.strftime('%Y-%m-%d')}). Threshold: {self.threshold_days} days.",
                )
            else:
                return CheckResultData(
                    status=CheckStatus.UP,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.NONE,
                    error_message=f"Domain registration valid ({days_left} days remaining until {expire_date.strftime('%Y-%m-%d')})",
                )

        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"RDAP domain lookup for '{domain}' timed out after {timeout}s",
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.UNKNOWN,
                error_message=f"Domain lookup failed: {str(exc)[:120]}",
            )
