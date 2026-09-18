"""
KeywordChecker — Strategy implementation for Content & Keyword verification checks.

Design:
- Fetches target URL via HTTP GET.
- Checks if a specific string or regular expression exists (or doesn't exist) in response body.
- Typical use-case: App returns HTTP 200 but renders "Database connection error" or blank page.
"""

import re
import time

import httpx

from checks.checkers.base import BaseChecker, CheckResultData
from checks.models import CheckErrorType, CheckStatus

MAX_BODY_SCAN_BYTES = 1024 * 512  # Scan up to 512 KB


class KeywordChecker(BaseChecker):
    """
    Validates page content against a keyword or regex pattern.
    """

    def __init__(self, monitor_data) -> None:
        super().__init__(monitor_data)
        self.keyword = monitor_data.get("keyword") or ""
        self.keyword_should_exist = monitor_data.get("keyword_should_exist", True)
        self.request_headers = monitor_data.get("request_headers") or {}

    def _execute(self, start_time: float) -> CheckResultData:
        url = self.url
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        timeout_config = httpx.Timeout(
            connect=float(self.timeout),
            read=float(self.timeout),
            write=float(self.timeout),
            pool=5.0,
        )

        try:
            with httpx.Client(
                timeout=timeout_config, follow_redirects=True, verify=True
            ) as client:
                headers = {
                    "User-Agent": "PetUptimeMonitor/1.0 (Keyword-Checker)",
                    **self.request_headers,
                }
                response = client.get(url, headers=headers)
                body_text = response.text[:MAX_BODY_SCAN_BYTES]

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Check keyword presence (case-insensitive substring or regex)
            found = False
            if self.keyword:
                try:
                    found = bool(re.search(self.keyword, body_text, re.IGNORECASE))
                except re.error:
                    found = self.keyword.lower() in body_text.lower()
            else:
                found = True

            if self.keyword_should_exist:
                if found:
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
                        error_type=CheckErrorType.KEYWORD_MISSING,
                        error_message=f"Required keyword '{self.keyword}' was not found in response content.",
                    )
            else:
                # keyword should NOT exist (e.g. error message check)
                if not found:
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
                        error_type=CheckErrorType.KEYWORD_PRESENT,
                        error_message=f"Forbidden keyword '{self.keyword}' was detected in response content.",
                    )

        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.TIMEOUT,
                error_message=f"Keyword check timed out after {self.timeout}s",
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.CONNECTION_ERROR,
                error_message=f"Keyword check failed: {str(exc)[:120]}",
            )
