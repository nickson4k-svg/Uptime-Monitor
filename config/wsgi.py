"""WSGI config for Pet Uptime Monitor (used for manage.py runserver, gunicorn, and Vercel)."""

import os
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

init_error = None
application = None

try:
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
except Exception:
    init_error = traceback.format_exc()


def app(environ, start_response):
    if init_error or application is None:
        err_msg = f"HTTP 500: Django Initialization Failed\n\n{init_error or 'Unknown initialization error'}"
        body = err_msg.encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    try:
        return application(environ, start_response)
    except Exception:
        runtime_err = traceback.format_exc()
        body = f"HTTP 500: Django Request Handler Failed\n\n{runtime_err}".encode()
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]
