from __future__ import annotations

import logging
import uuid

logger = logging.getLogger("apps.request")


class RequestIDMiddleware:
    """Attach a request id and echo it back for correlation."""

    header = "HTTP_X_REQUEST_ID"
    response_header = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(self.header) or uuid.uuid4().hex
        request.request_id = request_id
        response = self.get_response(request)
        response[self.response_header] = request_id
        return response


class SecurityHeadersMiddleware:
    """Add conservative security headers not covered by Django settings."""

    csp = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        headers = {
            "Content-Security-Policy": self.csp,
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        }
        for name, value in headers.items():
            if name not in response:
                response[name] = value
        return response
