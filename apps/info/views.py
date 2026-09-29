from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db.models import Q

from apps.scoping import scoped_info, scoped_infos
from .models import Info

MIN_AGE = 1
MAX_AGE = 150


def _parse_age(raw_age):
    try:
        return int(raw_age)
    except (TypeError, ValueError):
        return None


@login_required(login_url='login')
def info_list_page(request):
    query = request.GET.get('q', '').strip()

    infos_list = scoped_infos(request.user).order_by('name')

    if query:
        infos_list = infos_list.filter(
            Q(name__icontains=query) |
            Q(address__icontains=query) |
            Q(email__icontains=query)
        )

    paginator = Paginator(infos_list, 10)
    page_number = request.GET.get('page', 1)
    infos = paginator.get_page(page_number)

    return render(request, 'info.html', {
        'infos': infos,
        'query': query,
    })


@login_required(login_url='login')
def info_list_ajax(request):
    query = request.GET.get('q', '').strip()

    infos_list = scoped_infos(request.user).order_by('name')

    if query:
        infos_list = infos_list.filter(
            Q(name__icontains=query) |
            Q(address__icontains=query) |
            Q(email__icontains=query)
        )

    paginator = Paginator(infos_list, 10)
    page_number = request.GET.get('page', 1)
    infos = paginator.get_page(page_number)
    data = list(infos.object_list.values('id', 'name', 'age', 'address', 'email'))
    return JsonResponse({
        'data': data,
        'has_next': infos.has_next(),
        'has_prev': infos.has_previous(),
        'page': infos.number,
        'pages': infos.paginator.num_pages,
        'total': infos.paginator.count,
    })


@login_required(login_url='login')
def info_get_ajax(request, pk):
    info = scoped_info(request.user, pk)
    return JsonResponse({
        'id': info.id,
        'name': info.name,
        'age': info.age,
        'address': info.address,
        'email': info.email,
    })


@login_required(login_url='login')
@require_POST
def info_save_ajax(request):
    info_id = request.POST.get('id')

    if info_id:
        info = scoped_info(request.user, info_id)
    else:
        info = Info()

    name = request.POST.get('name', '').strip()
    age = request.POST.get('age', '').strip()
    address = request.POST.get('address', '').strip()
    email = request.POST.get('email', '').strip()

    if not name:
        return JsonResponse({'error': 'Name is required.'}, status=400)

    if not age:
        return JsonResponse({'error': 'Age is required.'}, status=400)

    age_value = _parse_age(age)

    if age_value is None or age_value < MIN_AGE or age_value > MAX_AGE:
        return JsonResponse(
            {'error': f'Age must be a number between {MIN_AGE} and {MAX_AGE}.'},
            status=400
        )

    if not address:
        return JsonResponse({'error': 'Address is required.'}, status=400)

    if email:
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({'error': 'Enter a valid email address.'}, status=400)

    info.name = name
    info.age = age_value
    info.address = address
    info.email = email

    if not info.pk:
        info.user = request.user

    try:
        info.save()
    except IntegrityError:
        return JsonResponse(
            {'error': 'Could not save record due to a conflict.'},
            status=400
        )

    return JsonResponse({
        'status': 'success',
        'id': info.id,
        'name': info.name,
        'age': info.age,
        'address': info.address,
        'email': info.email,
    })


@login_required(login_url='login')
@require_POST
def info_delete_ajax(request, pk):
    info = scoped_info(request.user, pk)
    info.delete()
    return JsonResponse({'status': 'deleted'})
