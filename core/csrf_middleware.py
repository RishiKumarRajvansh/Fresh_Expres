from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.middleware.csrf import CsrfViewMiddleware
from django.http import HttpResponseForbidden
from django.core.exceptions import MiddlewareNotUsed


class CustomCSRFMiddleware(MiddlewareMixin):
    """Custom CSRF middleware to redirect to login instead of showing 403"""
    
    def process_exception(self, request, exception):
        """Handle CSRF verification failures"""
        # Check if it's a CSRF verification failure
        if hasattr(exception, 'status_code') and exception.status_code == 403:
            # Check if the exception is CSRF related
            if 'CSRF' in str(exception) or 'Forbidden' in str(exception):
                # If user is not authenticated, redirect to login
                if not request.user.is_authenticated:
                    return redirect('accounts:customer_login')
                else:
                    # If authenticated user, show error message and redirect back
                    return redirect(request.META.get('HTTP_REFERER', '/'))
        
        return None
