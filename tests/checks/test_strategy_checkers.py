"""
Unit tests for Strategy Pattern Checkers:
- CheckerFactory
- HttpChecker
- KeywordChecker
- SSLCertChecker
- TCPChecker
- DomainExpiryChecker
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
import respx
import httpx

from checks.checkers.domain import DomainExpiryChecker
from checks.checkers.factory import CheckerFactory
from checks.checkers.http import HttpChecker
from checks.checkers.keyword import KeywordChecker
from checks.checkers.ssl_cert import SSLCertChecker
from checks.checkers.tcp import TCPChecker
from checks.models import CheckErrorType, CheckStatus
from monitors.models import MonitorType


@pytest.mark.unit
class TestCheckerFactory:
    def test_factory_resolves_http_checker(self):
        checker = CheckerFactory.get_checker({"monitor_type": MonitorType.HTTP, "url": "https://example.com"})
        assert isinstance(checker, HttpChecker)

    def test_factory_resolves_keyword_checker(self):
        checker = CheckerFactory.get_checker({"monitor_type": MonitorType.KEYWORD, "url": "https://example.com"})
        assert isinstance(checker, KeywordChecker)

    def test_factory_resolves_ssl_checker(self):
        checker = CheckerFactory.get_checker({"monitor_type": MonitorType.SSL, "url": "https://example.com"})
        assert isinstance(checker, SSLCertChecker)

    def test_factory_resolves_tcp_checker(self):
        checker = CheckerFactory.get_checker({"monitor_type": MonitorType.TCP, "url": "127.0.0.1:5432"})
        assert isinstance(checker, TCPChecker)

    def test_factory_resolves_domain_checker(self):
        checker = CheckerFactory.get_checker({"monitor_type": MonitorType.DOMAIN, "url": "example.com"})
        assert isinstance(checker, DomainExpiryChecker)

    def test_factory_defaults_to_http(self):
        checker = CheckerFactory.get_checker({"url": "https://example.com"})
        assert isinstance(checker, HttpChecker)


@pytest.mark.unit
class TestKeywordChecker:
    @respx.mock
    def test_keyword_found_returns_up(self):
        respx.get("https://example.com/status").mock(
            return_value=httpx.Response(200, text="<html><body>System Status: All Systems Operational</body></html>")
        )
        checker = KeywordChecker({
            "url": "https://example.com/status",
            "keyword": "All Systems Operational",
            "keyword_should_exist": True,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.UP
        assert result.http_code == 200
        assert result.error_type == CheckErrorType.NONE

    @respx.mock
    def test_keyword_missing_returns_down(self):
        respx.get("https://example.com/status").mock(
            return_value=httpx.Response(200, text="<html><body>503 Service Unavailable: Database Down</body></html>")
        )
        checker = KeywordChecker({
            "url": "https://example.com/status",
            "keyword": "Operational",
            "keyword_should_exist": True,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.KEYWORD_MISSING
        assert "not found" in result.error_message

    @respx.mock
    def test_forbidden_keyword_found_returns_down(self):
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text="Error: Fatal database connection deadlock")
        )
        checker = KeywordChecker({
            "url": "https://example.com",
            "keyword": "Fatal database connection",
            "keyword_should_exist": False,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.KEYWORD_PRESENT


@pytest.mark.unit
class TestSSLCertChecker:
    @patch("ssl.create_default_context")
    @patch("socket.create_connection")
    def test_ssl_valid_cert_returns_up(self, mock_socket_conn, mock_ssl_ctx):
        future_date = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%b %d %H:%M:%S %Y GMT")
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {"notAfter": future_date}
        
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssock
        mock_ssl_ctx.return_value = mock_context
        mock_socket_conn.return_value.__enter__.return_value = MagicMock()

        checker = SSLCertChecker({
            "url": "https://google.com",
            "ssl_threshold_days": 14,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.UP
        assert result.error_type == CheckErrorType.NONE
        assert "SSL valid" in result.error_message

    @patch("ssl.create_default_context")
    @patch("socket.create_connection")
    def test_ssl_expiring_soon_returns_down(self, mock_socket_conn, mock_ssl_ctx):
        expiring_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%b %d %H:%M:%S %Y GMT")
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {"notAfter": expiring_date}
        
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssock
        mock_ssl_ctx.return_value = mock_context
        mock_socket_conn.return_value.__enter__.return_value = MagicMock()

        checker = SSLCertChecker({
            "url": "https://example.com",
            "ssl_threshold_days": 14,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.SSL_EXPIRING_SOON
        assert "expires in" in result.error_message

    @patch("ssl.create_default_context")
    @patch("socket.create_connection")
    def test_ssl_expired_cert_returns_down(self, mock_socket_conn, mock_ssl_ctx):
        expired_date = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%b %d %H:%M:%S %Y GMT")
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {"notAfter": expired_date}
        
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssock
        mock_ssl_ctx.return_value = mock_context
        mock_socket_conn.return_value.__enter__.return_value = MagicMock()

        checker = SSLCertChecker({
            "url": "https://example.com",
            "ssl_threshold_days": 14,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.SSL_EXPIRED
        assert "expired" in result.error_message


@pytest.mark.unit
class TestTCPChecker:
    @patch("socket.socket")
    def test_tcp_open_port_returns_up(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.return_value = None

        checker = TCPChecker({
            "url": "127.0.0.1",
            "tcp_port": 5432,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.UP
        assert result.error_type == CheckErrorType.NONE
        assert "TCP connection established" in result.error_message

    @patch("socket.socket")
    def test_tcp_closed_port_returns_down(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        checker = TCPChecker({
            "url": "127.0.0.1",
            "tcp_port": 9999,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.TCP_CONNECTION_FAILED


@pytest.mark.unit
class TestDomainExpiryChecker:
    @respx.mock
    def test_domain_valid_returns_up(self):
        future_iso = (datetime.now(timezone.utc) + timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
        respx.get("https://rdap.org/domain/example.com").mock(
            return_value=httpx.Response(200, json={
                "events": [{"eventAction": "expiration", "eventDate": future_iso}]
            })
        )
        checker = DomainExpiryChecker({
            "url": "example.com",
            "domain_threshold_days": 30,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.UP
        assert result.error_type == CheckErrorType.NONE
        assert "Domain registration valid" in result.error_message

    @respx.mock
    def test_domain_expiring_soon_returns_down(self):
        expiring_iso = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        respx.get("https://rdap.org/domain/example.com").mock(
            return_value=httpx.Response(200, json={
                "events": [{"eventAction": "expiration", "eventDate": expiring_iso}]
            })
        )
        checker = DomainExpiryChecker({
            "url": "example.com",
            "domain_threshold_days": 30,
            "timeout": 5,
        })
        result = checker.run()
        assert result.status == CheckStatus.DOWN
        assert result.error_type == CheckErrorType.DOMAIN_EXPIRING_SOON
        assert "expires in" in result.error_message
