"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECURITY HEADERS MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Injects browser-level security headers across all outgoing HTTP responses:
# //   - X-Content-Type-Options: Blocks MIME-type sniffing
# //   - Referrer-Policy: Prevents token leakage in Referer headers
# //   - Permissions-Policy: Restricts sensors, allows camera for QR attendance scanning
# //   - Cross-Origin-Opener-Policy: Isolates browsing context against cross-origin attacks
# //   - X-XSS-Protection: 0 (OWASP modern standard, defers to CSP)
# //   - Content-Security-Policy: Mitigates XSS and script injection attacks
# // ==============================================================================
"""

from django.conf import settings

DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'self';"
)


class SecurityHeadersMiddleware:
    """
    // Injects defense-in-depth HTTP security headers into all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp_header = getattr(settings, 'CONTENT_SECURITY_POLICY', DEFAULT_CSP)

    def __call__(self, request):
        response = self.get_response(request)

        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(self)'
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('X-XSS-Protection', '0')

        if self.csp_header:
            response.headers.setdefault('Content-Security-Policy', self.csp_header)

        return response
