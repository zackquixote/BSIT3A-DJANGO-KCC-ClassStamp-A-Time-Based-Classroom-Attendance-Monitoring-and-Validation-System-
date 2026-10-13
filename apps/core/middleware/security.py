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
# // ==============================================================================
"""


class SecurityHeadersMiddleware:
    """
    // Injects defense-in-depth HTTP security headers into all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(self)'
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')

        return response
