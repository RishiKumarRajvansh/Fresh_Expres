from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from functools import wraps

def store_required(view_func):
    """
    Decorator that ensures only store owners and store staff can access the view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type not in ['store_owner', 'store_staff']:
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def delivery_agent_required(view_func):
    """
    Decorator that ensures only delivery agents can access the view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.user_type != 'delivery_agent':
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_required(view_func):
    """
    Decorator that ensures only admins can access the view
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff and request.user.user_type != 'admin':
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

class StoreRequiredMixin:
    """
    Mixin that ensures only store owners and store staff can access the view
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:email_login')
        
        if request.user.user_type not in ['store_owner', 'store_staff']:
            return redirect('core:home')
        
        return super().dispatch(request, *args, **kwargs)

class DeliveryAgentRequiredMixin:
    """
    Mixin that ensures only delivery agents can access the view
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:email_login')
        
        if request.user.user_type != 'delivery_agent':
            return redirect('core:home')
        
        return super().dispatch(request, *args, **kwargs)

class AdminRequiredMixin:
    """
    Mixin that ensures only admins can access the view
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:email_login')
        
        if not request.user.is_staff and request.user.user_type != 'admin':
            return redirect('core:home')
        
        return super().dispatch(request, *args, **kwargs)
