"""
TCPChecker — Strategy implementation for TCP port ping & service availability monitoring.

Design:
- Attempts a raw TCP socket connection to hostname:port.
- Measures exact TCP handshake round-trip latency.
- Validates non-HTTP services like Redis, PostgreSQL, MySQL, SMTP, SSH, etc.
"""

import contextlib
import socket
import time
from urllib.parse import urlparse

from checks.checkers.base import BaseChecker, CheckResultData
from checks.models import CheckErrorType, CheckStatus


class TCPChecker(BaseChecker):
    """
    Executes TCP handshake to verify port connectivity and latency.
    """

    def __init__(self, monitor_data) -> None:
        super().__init__(monitor_data)
        self.tcp_port = monitor_data.get("tcp_port")

    def _extract_host_port(self) -> tuple[str, int]:
        target = self.url.strip()
        port = self.tcp_port

        if ":" in target and not target.startswith("http"):
            parts = target.split(":")
            host = parts[0]
            if not port and len(parts) > 1 and parts[1].isdigit():
                port = int(parts[1])
        elif target.startswith(("http://", "https://")):
            parsed = urlparse(target)
            host = parsed.hostname or target
            if not port:
                port = parsed.port or (443 if target.startswith("https") else 80)
        else:
            host = target

        if not port:
            port = 80

        return host, int(port)

    def _execute(self, start_time: float) -> CheckResultData:
        hostname, port = self._extract_host_port()
        timeout = float(self.timeout)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect((hostname, port))
            sock.close()

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.UP,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.NONE,
                error_message=f"TCP connection established to {hostname}:{port} in {elapsed_ms}ms",
            )
        except TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"TCP connection to {hostname}:{port} timed out after {timeout}s",
            )
        except socket.gaierror:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.DNS_ERROR,
                error_message=f"DNS resolution failed for hostname '{hostname}'",
            )
        except (ConnectionRefusedError, OSError) as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TCP_CONNECTION_FAILED,
                error_message=f"TCP port {port} on {hostname} is closed or unreachable: {str(exc)[:100]}",
            )
        finally:
            with contextlib.suppress(Exception):
                sock.close()
