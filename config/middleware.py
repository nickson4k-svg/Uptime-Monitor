"""
Request-ID correlation middleware and context tracking.
"""

import contextvars
import uuid

# Context variable to hold the request ID for the current async/thread task
request_id_ctx = contextvars.ContextVar("request_id", default=None)


def get_current_request_id() -> str | None:
    return request_id_ctx.get()


class RequestIDMiddleware:
    """
    Assigns or extracts an X-Request-ID for every incoming HTTP request.
    Attaches the request ID to the request object, response headers, and contextvars.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Read from incoming header or generate new UUID4
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.id = req_id
        token = request_id_ctx.set(req_id)

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)
