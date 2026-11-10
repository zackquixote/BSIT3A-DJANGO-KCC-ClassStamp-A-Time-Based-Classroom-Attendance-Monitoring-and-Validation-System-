import json

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import AuditEvent


@require_GET
def service_worker(request):
    response = render(
        request,
        'service-worker.js',
        content_type='application/javascript',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


CSP_REPORT_MAX_BYTES = 8192
CSP_REPORT_MAX_PER_WINDOW = 30
CSP_REPORT_WINDOW_SECONDS = 60


def _bump_counter(key, window):
    """Atomically increment a fixed-window counter, creating it with a TTL."""
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, window)
        return 1


@csrf_exempt
@require_POST
def csp_report(request):
    """
    // Bounded CSP violation collector.
    //
    // Browser report-uri POSTs carry no CSRF token, hence csrf_exempt.
    // JSON size and shape are validated; reports are rate-limited per IP so
    // a flood cannot fill the audit table. The /api/ prefix also puts the
    // endpoint behind RateLimitMiddleware.
    """
    if request.body and len(request.body) > CSP_REPORT_MAX_BYTES:
        return JsonResponse({'error': 'Report too large.'}, status=413)

    ip = request.META.get('REMOTE_ADDR', 'unknown')
    hits = _bump_counter(
        f'classstamp:csp:rl:{ip}', CSP_REPORT_WINDOW_SECONDS,
    )
    if hits > CSP_REPORT_MAX_PER_WINDOW:
        return JsonResponse({'error': 'Too many reports.'}, status=429)

    try:
        payload = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'error': 'Invalid report shape.'}, status=400)

    report = payload.get('csp-report')
    if not isinstance(report, dict):
        report = payload

    directive = str(
        report.get('violated-directive') or report.get('effective-directive') or ''
    )[:80]
    blocked_uri = str(report.get('blocked-uri') or '')[:200]
    source_file = str(report.get('source-file') or '')[:200]
    line_number = report.get('line-number')

    AuditEvent.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action='CSP_VIOLATION',
        object_type='CspReport',
        object_id=None,
        reason=(
            f'directive={directive} blocked={blocked_uri} '
            f'source={source_file} line={line_number}'
        ),
    )
    return JsonResponse({'ok': True}, status=201)
