from django.shortcuts import render
from django.views.decorators.http import require_GET


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
