"""
# // ==============================================================================
# // KCC CLASSSTAMP - BROWSER CACHE CONTROL MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Attaches strict Cache-Control headers to HTML responses, preventing
# //   authenticated pages from being restored via browser back button history.
# // ==============================================================================
"""

from django.utils.cache import add_never_cache_headers


class DisableBrowserCacheMiddleware:
    """
    // Attaches 'Cache-Control: max-age=0, no-cache, no-store, must-revalidate'
    // headers to dynamic HTML responses, preventing bfcache leaks upon logout.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type:
            add_never_cache_headers(response)
            response['Pragma'] = 'no-cache'

        return response
