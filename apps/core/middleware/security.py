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
# //   - Content-Security-Policy / Content-Security-Policy-Report-Only
# //
# // CSP nonce:
# //   Generated per request and stored ONLY on request.csp_nonce. A middleware
# //   instance is shared across threads; storing the nonce on `self` would
# //   leak one request's nonce into another request's response.
# //
# // Enforcement:
# //   CSP_ENFORCE=False (default) sends Content-Security-Policy-Report-Only so
# //   inline scripts can be nonced or externalized before the policy bites.
# //   Flip CSP_ENFORCE=True only after browser verification (task 6.3).
# //
# // Single source of truth:
# //   The CSP_* tuples in mysite/settings/base.py. The old hardcoded
# //   DEFAULT_CSP (with unused CDN origins and script 'unsafe-inline') is gone.
# // ==============================================================================
"""

import secrets

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    // Injects defense-in-depth HTTP security headers into all responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp_enabled = getattr(settings, 'CSP_ENABLED', True)
        self.csp_enforce = getattr(settings, 'CSP_ENFORCE', False)

    def __call__(self, request):
        # Per-request nonce, stored on the request only (thread-safe).
        request.csp_nonce = secrets.token_urlsafe(16)

        response = self.get_response(request)

        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(self)'
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('X-XSS-Protection', '0')

        if self.csp_enabled:
            policy = self._build_csp_policy(request.csp_nonce)
            header_name = (
                'Content-Security-Policy'
                if self.csp_enforce
                else 'Content-Security-Policy-Report-Only'
            )
            # Do not clobber a header an earlier layer may already have set.
            response.headers.setdefault(header_name, policy)

        return response

    def _build_csp_policy(self, nonce: str) -> str:
        """
        // Build the policy string from the CSP_* setting tuples.
        // script-src gains this request's nonce and must not include
        // 'unsafe-inline'. style-src keeps 'unsafe-inline' until the 20+
        // legacy style blocks and Django admin are migrated.
        """

        def sources(setting_name, fallback):
            parts = getattr(settings, setting_name, None) or fallback
            return ' '.join(parts)

        default_src = sources('CSP_DEFAULT_SRC', ["'self'"])
        script_src = sources('CSP_SCRIPT_SRC', ["'self'"])
        style_src = sources('CSP_STYLE_SRC', ["'self'", "'unsafe-inline'"])
        img_src = sources('CSP_IMG_SRC', ["'self'", 'data:', 'blob:'])
        font_src = sources('CSP_FONT_SRC', ["'self'", 'data:'])
        connect_src = sources('CSP_CONNECT_SRC', ["'self'"])
        frame_ancestors = sources('CSP_FRAME_ANCESTORS', ["'self'"])
        base_uri = sources('CSP_BASE_URI', ["'self'"])
        form_action = sources('CSP_FORM_ACTION', ["'self'"])

        policy_parts = [
            'default-src ' + default_src,
            'script-src ' + script_src + " 'nonce-" + nonce + "'",
            'style-src ' + style_src,
            'img-src ' + img_src,
            'font-src ' + font_src,
            'connect-src ' + connect_src,
            'frame-ancestors ' + frame_ancestors,
            'base-uri ' + base_uri,
            'form-action ' + form_action,
        ]
        if getattr(settings, 'CSP_REPORTING', True):
            policy_parts.append('report-uri /api/csp-report/')
        return '; '.join(policy_parts)
