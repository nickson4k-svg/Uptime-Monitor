"""
HttpChecker — Strategy implementation for standard HTTP/HTTPS status code checks.
"""

import time
import httpx

from checks.checkers.base import BaseChecker, CheckResultData
from checks.models import CheckErrorType, CheckStatus

MAX_RESPONSE_BYTES = 1024 * 10  # 10 KB


class HttpChecker(BaseChecker):
    """
    Executes standard HTTP(S) health checks against an endpoint.
    Verifies response status code matches expected_status_code.
    """

    def __init__(self, monitor_data) -> None:
        super().__init__(monitor_data)
        self.method = monitor_data.get("method", "GET")
        self.expected_status_code = monitor_data.get("expected_status_code", 200)
        self.request_headers = monitor_data.get("request_headers") or {}
        self.request_body = monitor_data.get("request_body") or ""

    def _execute(self, start_time: float) -> CheckResultData:
        url = self.url
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)
        timeout_config = httpx.Timeout(
            connect=float(self.timeout),
            read=float(self.timeout),
            write=float(self.timeout),
            pool=5.0,
        )

        try:
            with httpx.Client(
                timeout=timeout_config,
                limits=limits,
                follow_redirects=True,
                max_redirects=10,
                verify=True,
            ) as client:
                headers = {
                    "User-Agent": "PetUptimeMonitor/1.0 (+https://github.com/nickson4k/Pet-Uptime-Monitor)",
                    **self.request_headers,
                }

                req_kwargs = {
                    "method": self.method,
                    "url": url,
                    "headers": headers,
                }
                if self.request_body and self.method in ("POST", "PUT", "PATCH"):
                    req_kwargs["content"] = self.request_body.encode("utf-8")

                response = client.request(**req_kwargs)
                response.read()

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == self.expected_status_code:
                return CheckResultData(
                    status=CheckStatus.UP,
                    response_time_ms=elapsed_ms,
                    http_code=response.status_code,
                    error_type=CheckErrorType.NONE,
                    error_message="",
                )
            else:
                return CheckResultData(
                    status=CheckStatus.DOWN,
                    response_time_ms=elapsed_ms,
                    http_code=response.status_code,
                    error_type=CheckErrorType.HTTP_ERROR,
                    error_message=f"Expected {self.expected_status_code}, got {response.status_code}",
                )

        except httpx.ConnectTimeout:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"Connection timed out after {self.timeout}s",
            )
        except httpx.ReadTimeout:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"Read timed out after {self.timeout}s",
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            exc_str = str(exc).lower()
            if "name or service not known" in exc_str or "getaddrinfo failed" in exc_str or "nodename" in exc_str:
                error_type = CheckErrorType.DNS_ERROR
                msg = "DNS resolution failed"
            elif "ssl" in exc_str or "certificate" in exc_str or "tls" in exc_str:
                error_type = CheckErrorType.SSL_ERROR
                msg = f"SSL certificate verification failed: {str(exc)[:100]}"
            else:
                error_type = CheckErrorType.CONNECTION_ERROR
                msg = f"Connection refused or network unreachable: {str(exc)[:100]}"

            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=error_type,
                error_message=msg,
            )
        except httpx.TooManyRedirects:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TOO_MANY_REDIRECTS,
                error_message="Exceeded maximum redirect limit (>10 redirects)",
            )
        except httpx.HTTPError as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            exc_str = str(exc).lower()
            if "ssl" in exc_str or "certificate" in exc_str:
                error_type = CheckErrorType.SSL_ERROR
            else:
                error_type = CheckErrorType.CONNECTION_ERROR

            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=error_type,
                error_message=f"HTTP protocol error: {str(exc)[:120]}",
            )
