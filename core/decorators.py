from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def admin_required(view_func):
    """
    Decorador para restringir el acceso exclusivamente a usuarios con rol de Administrador.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debe iniciar sesión para acceder a este recurso.')
            return redirect('core:login')
        
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, 'Acceso denegado: Se requieren permisos de Administrador.')
        return redirect('core:dashboard')
    
    return _wrapped_view


def role_required(allowed_roles=None):
    """
    Decorador genérico para permitir el acceso a una lista de roles autorizados.
    Ejemplo: @role_required(['admin', 'employee'])
    """
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Debe iniciar sesión para acceder a este recurso.')
                return redirect('core:login')

            if hasattr(request.user, 'profile'):
                if request.user.profile.role in allowed_roles or request.user.is_superuser:
                    return view_func(request, *args, **kwargs)

            messages.error(request, 'No tiene los permisos requeridos para acceder a este módulo.')
            return redirect('core:dashboard')
        return _wrapped_view
    return decorator
