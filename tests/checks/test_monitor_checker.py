"""
Unit tests for MonitorChecker service.

Tests cover all error classification edge cases:
- Timeout (connect timeout, read timeout)
- DNS failure
- SSL error
- Too many redirects
- HTTP status mismatch (200 expected, 500 received)
- UP (correct status code)
- Flapping (UP → DOWN → UP is handled by IncidentService, not Checker)

MonitorChecker is a pure service class — no DB needed.
All HTTP calls are mocked with respx (httpx mocker).
"""

import httpx
import pytest
import respx

from checks.models import CheckErrorType, CheckStatus
from checks.services import MonitorChecker


@pytest.fixture
def monitor_data():
    return {
        "url": "https://example.com",
        "method": "GET",
        "timeout": 10,
        "expected_status_code": 200,
        "request_headers": {},
        "request_body": "",
    }


@pytest.mark.unit
class TestMonitorCheckerUp:
    @respx.mock
    def test_returns_up_on_correct_status_code(self, monitor_data):
        respx.get("https://example.com").mock(return_value=httpx.Response(200))

        checker = MonitorChecker(monitor_data)
        result = checker.run()

        assert result.status == CheckStatus.UP
        assert result.http_code == 200
        assert result.error_type == CheckErrorType.NONE
        assert result.error_message == ""
        assert result.response_time_ms is not None
        assert result.response_time_ms >= 0

    @respx.mock
    def test_records_response_time(self, monitor_data):
        respx.get("https://example.com").mock(return_value=httpx.Response(200))

        checker = MonitorChecker(monitor_data)
        result = checker.run()

        assert isinstance(result.response_time_ms, int)
        assert result.response_time_ms >= 0


@pytest.mark.unit
class TestMonitorCheckerDown:
    @respx.mock
    def test_returns_down_on_unexpected_status_code(self, monitor_data):
        """500 received, 200 expected → DOWN with HTTP_ERROR."""
        respx.get("https://example.com").mock(return_value=httpx.Response(500))

        checker = MonitorChecker(monitor_data)
        result = checker.run()

        assert result.status == CheckStatus.DOWN
        assert result.http_code == 500
        assert result.error_type == CheckErrorType.HTTP_ERROR
        assert "500" in result.error_message
        assert "200" in result.error_message

    @respx.mock
    def test_returns_down_on_404(self, monitor_data):
        respx.get("https://example.com").mock(return_value=httpx.Response(404))

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.HTTP_ERROR

    @respx.mock
    def test_expected_non_200_returns_up(self, monitor_data):
        """If expected_status_code=404 and server returns 404, it's UP."""
        monitor_data["expected_status_code"] = 404
        respx.get("https://example.com").mock(return_value=httpx.Response(404))

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.UP
        assert result.http_code == 404


@pytest.mark.unit
class TestMonitorCheckerTimeout:
    @respx.mock
    def test_connect_timeout_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.ConnectTimeout("timed out")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.TIMEOUT
        assert (
            "timed out" in result.error_message.lower()
            or "timeout" in result.error_message.lower()
        )

    @respx.mock
    def test_read_timeout_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.ReadTimeout("read timed out")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.TIMEOUT


@pytest.mark.unit
class TestMonitorCheckerConnectionErrors:
    @respx.mock
    def test_dns_failure_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.ConnectError("Name or service not known")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.DNS_ERROR

    @respx.mock
    def test_connection_refused_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.CONNECTION_ERROR

    @respx.mock
    def test_ssl_error_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.ConnectError("SSL certificate verification failed")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.SSL_ERROR

    @respx.mock
    def test_too_many_redirects_returns_down(self, monitor_data):
        respx.get("https://example.com").mock(
            side_effect=httpx.TooManyRedirects("Exceeded maximum redirects")
        )

        result = MonitorChecker(monitor_data).run()

        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.TOO_MANY_REDIRECTS


@pytest.mark.unit
class TestMonitorCheckerProperties:
    @respx.mock
    def test_is_up_property(self, monitor_data):
        respx.get("https://example.com").mock(return_value=httpx.Response(200))
        result = MonitorChecker(monitor_data).run()
        assert result.is_up is True
        assert result.is_down is False

    @respx.mock
    def test_is_down_property(self, monitor_data):
        respx.get("https://example.com").mock(return_value=httpx.Response(503))
        result = MonitorChecker(monitor_data).run()
        assert result.is_down is True
        assert result.is_up is False

    def test_never_raises_exception(self, monitor_data):
        """MonitorChecker.run() must never raise — even on unexpected errors."""
        monitor_data["url"] = "not-a-url-at-all"
        result = MonitorChecker(monitor_data).run()
        assert result.status == CheckStatus.DOWN
