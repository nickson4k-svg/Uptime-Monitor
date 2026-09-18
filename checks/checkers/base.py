"""
BaseChecker — Abstract Strategy Base Class for all monitor check protocols.

Architecture:
- Implements Strategy Pattern.
- Standardizes CheckResultData dataclass across all protocols.
- Handles time measurement, safe execution, and structured error classification.
"""

import abc
import time
from dataclasses import dataclass
from typing import Any

from checks.models import CheckErrorType, CheckStatus


@dataclass
class CheckResultData:
    """
    Immutable result of a single health probe.
    DB-agnostic dataclass returned by all Strategy Checkers.
    """

    status: str  # CheckStatus.UP or CheckStatus.DOWN
    response_time_ms: int | None  # None if connection failed entirely
    http_code: int | None  # None for non-HTTP checks (or if connection failed)
    error_type: str  # CheckErrorType value
    error_message: str

    @property
    def is_up(self) -> bool:
        return self.status == CheckStatus.UP

    @property
    def is_down(self) -> bool:
        return self.status == CheckStatus.DOWN


class BaseChecker(abc.ABC):
    """
    Abstract Strategy class for monitor checkers.
    Each protocol subclass implements _execute() and handles its specific network probing logic.
    """

    def __init__(self, monitor_data: dict[str, Any]) -> None:
        self.data = monitor_data
        self.url = monitor_data.get("url", "")
        self.timeout = monitor_data.get("timeout", 10)

    def run(self) -> CheckResultData:
        """
        Template method executing the probe with latency timing and top-level exception guards.
        """
        start_time = time.monotonic()
        try:
            result = self._execute(start_time)
            return result
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return CheckResultData(
                status=CheckStatus.DOWN,
                response_time_ms=elapsed_ms,
                http_code=None,
                error_type=CheckErrorType.UNKNOWN,
                error_message=f"Unexpected checker error: {str(exc)}",
            )

    @abc.abstractmethod
    def _execute(self, start_time: float) -> CheckResultData:
        """
        Execute the protocol-specific check.
        Must return CheckResultData.
        """
        raise NotImplementedError
