from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Profile


def vendor_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = Profile.objects.filter(user=request.user).first()
        if not profile or profile.role != Profile.Role.VENDOR or not hasattr(request.user, 'store'):
            messages.error(request, 'Área exclusiva para vendedores.')
            return redirect('home')
        return view_func(request, *args, **kwargs)

    return wrapper
