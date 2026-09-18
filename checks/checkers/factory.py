"""
CheckerFactory — Factory & Registry for Strategy Checkers.

Dispatches monitor checks based on MonitorType.
"""

from typing import Any

from checks.checkers.base import BaseChecker
from checks.checkers.domain import DomainExpiryChecker
from checks.checkers.http import HttpChecker
from checks.checkers.keyword import KeywordChecker
from checks.checkers.ssl_cert import SSLCertChecker
from checks.checkers.tcp import TCPChecker
from monitors.models import MonitorType


class CheckerFactory:
    """
    Factory Registry mapping MonitorType -> BaseChecker subclass.
    """

    _registry: dict[str, type[BaseChecker]] = {
        MonitorType.HTTP: HttpChecker,
        MonitorType.KEYWORD: KeywordChecker,
        MonitorType.SSL: SSLCertChecker,
        MonitorType.TCP: TCPChecker,
        MonitorType.DOMAIN: DomainExpiryChecker,
    }

    @classmethod
    def register(cls, monitor_type: str, checker_cls: type[BaseChecker]) -> None:
        """Register a custom protocol checker."""
        cls._registry[monitor_type] = checker_cls

    @classmethod
    def get_checker(cls, monitor_data: Any) -> BaseChecker:
        """
        Instantiate the appropriate checker for the given monitor data or model instance.
        """
        if hasattr(monitor_data, "monitor_type"):
            m_type = monitor_data.monitor_type
            # Extract dict for checker
            data = {
                "id": monitor_data.id,
                "monitor_type": m_type,
                "url": monitor_data.url,
                "method": monitor_data.method,
                "timeout": monitor_data.timeout,
                "expected_status_code": monitor_data.expected_status_code,
                "request_headers": monitor_data.request_headers,
                "request_body": monitor_data.request_body,
                "keyword": monitor_data.keyword,
                "keyword_should_exist": monitor_data.keyword_should_exist,
                "tcp_port": monitor_data.tcp_port,
                "ssl_threshold_days": monitor_data.ssl_threshold_days,
                "domain_threshold_days": monitor_data.domain_threshold_days,
            }
        else:
            m_type = monitor_data.get("monitor_type", MonitorType.HTTP)
            data = monitor_data

        checker_cls = cls._registry.get(m_type, HttpChecker)
        return checker_cls(data)
