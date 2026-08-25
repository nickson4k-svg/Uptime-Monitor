"""
SSLCertChecker — Strategy implementation for SSL / TLS certificate validity and expiry monitoring.

Design:
- Performs TLS handshake with SNI (Server Name Indication).
- Retrieves and validates certificate chain.
- Computes days remaining until expiration.
- Triggers alert if days remaining <= ssl_threshold_days.
"""

from datetime import datetime, timezone
import socket
import ssl
import time
from urllib.parse import urlparse

from checks.checkers.base import BaseChecker, CheckResultData
from checks.models import CheckErrorType, CheckStatus


class SSLCertChecker(BaseChecker):
    """
    Checks SSL certificate validity and warns if expiration date is near.
    """

    def __init__(self, monitor_data) -> None:
        super().__init__(monitor_data)
        self.threshold_days = int(monitor_data.get("ssl_threshold_days") or 14)

    def _extract_host_port(self) -> tuple[str, int]:
        target = self.url.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        parsed = urlparse(target)
        host = parsed.hostname or self.url
        port = parsed.port or 443
        return host, port

    def _execute(self, start_time: float) -> CheckResultData:
        hostname, port = self._extract_host_port()
        timeout = float(self.timeout)

        context = ssl.create_default_context()

        try:
            with socket.create_connection((hostname, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if not cert or "notAfter" not in cert:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.SSL_ERROR,
                    error_message="Could not retrieve SSL certificate details.",
                )

            # Parse SSL expiration date format (e.g. 'May 15 12:00:00 2027 GMT')
            not_after_str = cert["notAfter"]
            expire_date = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)

            remaining_delta = expire_date - now
            days_left = remaining_delta.days

            if days_left < 0:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.SSL_EXPIRED,
                    error_message=f"SSL certificate for {hostname} expired {abs(days_left)} days ago ({expire_date.strftime('%Y-%m-%d')}).",
                )
            elif days_left <= self.threshold_days:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.SSL_EXPIRING_SOON,
                    error_message=f"SSL certificate for {hostname} expires in {days_left} days ({expire_date.strftime('%Y-%m-%d')}). Threshold: {self.threshold_days} days.",
                )
            else:
                return CheckResultData(
                    status=CheckStatus.UP,
                    response_time_ms=elapsed_ms,
                    http_code=None,
                    error_type=CheckErrorType.NONE,
                    error_message=f"SSL valid ({days_left} days remaining until {expire_date.strftime('%Y-%m-%d')})",
                )

        except ssl.SSLCertVerificationError as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.SSL_ERROR,
                error_message=f"SSL certificate verification failed: {exc.verify_message}",
            )
        except (socket.timeout, TimeoutError):
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"SSL connection to {hostname}:{port} timed out after {timeout}s",
            )
        except (socket.gaierror, ConnectionRefusedError, OSError) as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.CONNECTION_ERROR,
                error_message=f"Could not connect to {hostname}:{port}: {str(exc)[:100]}",
            )
