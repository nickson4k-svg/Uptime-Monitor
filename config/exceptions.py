"""Custom DRF exception handler — consistent error response format."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wrap all DRF exceptions in a consistent envelope:
    {
        "error": {
            "code": "validation_error",
            "message": "...",
            "details": {...}
        }
    }
    """
    # Convert Django ValidationError to DRF ValidationError
    if isinstance(exc, DjangoValidationError):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            "error": {
                "code": _get_error_code(exc),
                "message": _get_error_message(exc),
                "details": response.data,
            }
        }
        response.data = error_payload
    else:
        # Unhandled exception — return 500
        logger.exception("Unhandled exception in %s", context.get("view"))
        response = Response(
            {
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _get_error_code(exc) -> str:
    if hasattr(exc, "default_code"):
        return exc.default_code
    return type(exc).__name__.lower()


def _get_error_message(exc) -> str:
    if hasattr(exc, "detail"):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            return str(detail[0])
    return str(exc)
