"""
MonitorChecker service — Facade for Strategy Pattern Checkers.
"""

import logging
from checks.checkers.base import CheckResultData
from checks.checkers.factory import CheckerFactory

logger = logging.getLogger(__name__)

# Re-export for compatibility
__all__ = ["CheckResultData", "MonitorChecker", "CheckerFactory"]


class MonitorChecker:
    """
    Facade maintaining backwards-compatibility for MonitorChecker.
    Delegates check execution to CheckerFactory strategy.
    """

    def __init__(self, monitor) -> None:
        self.checker = CheckerFactory.get_checker(monitor)
        if hasattr(monitor, "url"):
            self.url = monitor.url
            self.timeout = monitor.timeout
        else:
            self.url = monitor.get("url", "")
            self.timeout = monitor.get("timeout", 10)

    def run(self) -> CheckResultData:
        return self.checker.run()
