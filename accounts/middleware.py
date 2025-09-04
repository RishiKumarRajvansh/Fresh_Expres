from django.shortcuts import redirect
from django.urls import reverse
from django.http import Http404
import logging


class UserTypeAccessMiddleware:
    """
    Middleware to restrict access based on user type.
    - Customers: Only customer pages
    - Store owners/staff: Only store pages  
    - Delivery agents: Only delivery pages
    - Admin: Can access admin panel and has override access
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger = logging.getLogger(__name__)
        # Skip for non-authenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superusers (they have full access)
        if request.user.is_superuser:
            return self.get_response(request)

        path = request.path_info
        
        # Skip media files and static files - they should be accessible to all authenticated users
        if path.startswith('/media/') or path.startswith('/static/'):
            return self.get_response(request)
        
        # Allow certain account endpoints for all authenticated users (logout, business login)
        # This prevents the middleware from blocking access to logout and business login pages.
        if path.startswith('/accounts/logout') or path.startswith('/accounts/email-login') or path.startswith('/accounts/business-register'):
            logger.debug(f"UserTypeAccessMiddleware: allowing access to auth endpoint: {path} for user={getattr(request.user, 'username', None)} type={getattr(request.user, 'user_type', None)}")
            return self.get_response(request)

        user_type = getattr(request.user, 'user_type', 'customer')
        
        # Define URL patterns and their allowed user types
        access_rules = {
            'admin': {
                'allowed_paths': ['/admin/', '/core/admin/', '/accounts/admin/'],
                'allowed_users': ['admin'],
                'redirect_url': '/admin/login/',
            },
            'store': {
                'allowed_paths': ['/stores/', '/dashboards/store/', '/core/store/', '/delivery/store/'],
                'allowed_users': ['store_owner', 'store_staff'],
                'redirect_url': 'accounts:email_login',
            },
            'delivery': {
                'allowed_paths': ['/delivery/', '/dashboards/delivery/', '/core/delivery/'],
                'allowed_users': ['delivery_agent'],
                'redirect_url': 'accounts:email_login',
            },
            'customer': {
                'allowed_paths': ['/orders/', '/catalog/', '/accounts/', '/core/', '/'],
                'allowed_users': ['customer'],
                'redirect_url': 'core:home',
            }
        }
        
        # Check each rule
        for rule_name, rule_data in access_rules.items():
            # Check if current path matches this rule
            if any(path.startswith(allowed_path) for allowed_path in rule_data['allowed_paths']):
                # If user type is not allowed for this path, redirect them
                if user_type not in rule_data['allowed_users']:
                    # Special handling for admin paths
                    if rule_name == 'admin':
                        logger.info(f"UserTypeAccessMiddleware: redirecting user={getattr(request.user,'username',None)} path={path} -> core:home")
                        return redirect('core:home')
                    
                    # Special handling for store paths
                    elif rule_name == 'store':
                        if user_type == 'customer':
                            logger.info(f"UserTypeAccessMiddleware: redirecting customer user={getattr(request.user,'username',None)} path={path} -> core:home")
                            return redirect('core:home')
                        elif user_type == 'delivery_agent':
                            logger.info(f"UserTypeAccessMiddleware: redirecting delivery agent user={getattr(request.user,'username',None)} path={path} -> delivery:agent_dashboard")
                            return redirect('delivery:agent_dashboard')
                        else:
                            logger.info(f"UserTypeAccessMiddleware: redirecting user={getattr(request.user,'username',None)} path={path} -> accounts:email_login")
                            return redirect('accounts:email_login')
                    
                    # Special handling for delivery paths  
                    elif rule_name == 'delivery':
                        if user_type == 'customer':
                            logger.info(f"UserTypeAccessMiddleware: redirecting customer user={getattr(request.user,'username',None)} path={path} -> core:home")
                            return redirect('core:home')
                        elif user_type in ['store_owner', 'store_staff']:
                            logger.info(f"UserTypeAccessMiddleware: redirecting store user={getattr(request.user,'username',None)} path={path} -> stores:dashboard")
                            return redirect('stores:dashboard')
                        else:
                            logger.info(f"UserTypeAccessMiddleware: redirecting other user={getattr(request.user,'username',None)} path={path} -> accounts:email_login")
                            return redirect('accounts:email_login')
                    
                    # For customer paths, redirect non-customers appropriately
                    elif rule_name == 'customer':
                        if user_type in ['store_owner', 'store_staff']:
                            return redirect('stores:dashboard')
                        elif user_type == 'delivery_agent':
                            return redirect('delivery:agent_dashboard') 
                        elif user_type == 'admin':
                            return redirect('/admin/')
                    
                # If user type is allowed, continue
                break
        
        response = self.get_response(request)
        return response


class StoreAccessMiddleware:
    """
    Additional middleware to ensure store staff can only access their assigned store.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Only apply to store staff (not owners)
        if getattr(request.user, 'user_type', '') != 'store_staff':
            return self.get_response(request)
        
        path = request.path_info
        
        # If accessing store-specific URLs, check if they have access to that store
        if path.startswith('/stores/') and hasattr(request.user, 'store_staff_profile'):
            # Extract store ID from URL if present
            # This would need to be implemented based on your URL structure
            pass
        
        response = self.get_response(request)
        return response
