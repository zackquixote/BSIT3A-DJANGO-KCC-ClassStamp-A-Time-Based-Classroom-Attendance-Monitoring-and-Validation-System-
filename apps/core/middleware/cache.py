"""
# // ==============================================================================
# // KCC CLASSSTAMP - BROWSER CACHE CONTROL MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Attaches strict Cache-Control headers to HTML, redirects, and sensitive
# //   API responses, preventing authenticated pages and student records from being
# //   restored via browser back button history (bfcache) or intermediate proxy caches.
# // ==============================================================================
"""

from django.utils.cache import add_never_cache_headers


class DisableBrowserCacheMiddleware:
    """
    // Attaches 'Cache-Control: max-age=0, no-cache, no-store, must-revalidate'
    // headers to dynamic HTML responses, redirects, and authenticated API payloads,
    // preventing bfcache leaks upon logout and protecting sensitive student PII.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        content_type = response.get('Content-Type', '')
        is_html = 'text/html' in content_type
        is_redirect = 300 <= response.status_code < 400
        is_sensitive_json = (
            'application/json' in content_type
            and (
                (getattr(request, 'user', None) and request.user.is_authenticated)
                or request.path.startswith('/api/')
            )
        )

        if is_html or is_redirect or is_sensitive_json:
            add_never_cache_headers(response)
            response['Pragma'] = 'no-cache'

        return response
