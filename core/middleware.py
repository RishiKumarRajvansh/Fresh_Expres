from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
import re

class ZipCodeMiddleware(MiddlewareMixin):
    """Middleware to handle ZIP code sessions and redirects"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Get the current path
        current_path = request.path
        
        # List of exact patterns that don't require ZIP code
        if (current_path.startswith('/admin/') or
            current_path.startswith('/zip/') or
            current_path.startswith('/auth/login/') or
            current_path.startswith('/auth/register/') or
            current_path.startswith('/accounts/') or  # Allow all account operations
            current_path.startswith('/stores/') or   # Store owner dashboards
            current_path.startswith('/delivery/') or # Delivery agent dashboards
            current_path.startswith('/dashboard/') or # Core dashboard system
            current_path.startswith('/payments/') or  # Payment callbacks and webhooks
            current_path.startswith('/debug/') or    # Debug pages
            current_path.startswith('/manual-test/') or  # Test pages
            current_path.startswith('/simple-cart-test/') or  # Simple cart test
            current_path.startswith('/orders/cart/') or  # Cart pages
            current_path.startswith('/static/') or
            current_path.startswith('/media/') or
            current_path.startswith('/api/') or
            current_path == '/favicon.ico' or
            current_path.startswith('/.well-known/')):
            return None
        
        # Check if user has selected a ZIP code
        if not request.session.get('selected_zip_code'):
            # If this is an AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'error': 'ZIP code required', 'redirect': '/zip/'})
            
            # Redirect to ZIP capture page
            return redirect('/zip/')
        
        return None

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses"""
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
