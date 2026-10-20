"""
# // ==============================================================================
# // KCC CLASSSTAMP - REQUEST CORRELATION ID MIDDLEWARE
# // ==============================================================================
# // Subsystem: Observability & Security Audit Trail Tracking
# // Description: Injects a unique tracing UUID (`request.id`) into each HTTP request
# //   and returns it via the `X-Request-ID` response header, linking audit logs,
# //   attendance stamps, and error traces across distributed requests.
# // ==============================================================================
"""

import uuid


class RequestCorrelationIdMiddleware:
    """
    // Assigns a unique correlation ID to `request.id` and emits `X-Request-ID`.
    // Reuses an existing inbound `X-Request-ID` from an upstream proxy if present.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
        request.id = request_id

        response = self.get_response(request)
        response.headers['X-Request-ID'] = request_id
        return response
