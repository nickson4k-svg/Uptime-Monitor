"""
Structured JSON log formatter for production observability.
"""

import datetime
import json
import logging
from config.middleware import get_current_request_id


class StructuredJSONFormatter(logging.Formatter):
    """
    Formats log records as structured single-line JSON objects, ideal for
    Fluentbit, Vector, Datadog, CloudWatch, or ELK ingestion.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_current_request_id(),
            "module": record.module,
            "line": record.lineno,
        }

        # Extra attributes passed via logger.info("...", extra={...})
        if hasattr(record, "monitor_id"):
            log_data["monitor_id"] = record.monitor_id
        if hasattr(record, "region"):
            log_data["region"] = record.region

        # Exception information
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)
