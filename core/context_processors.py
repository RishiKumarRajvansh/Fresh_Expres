from django.conf import settings

def global_context(request):
    """Global context processor for all templates"""
    context = {
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        'MEDIA_URL': settings.MEDIA_URL,
        'selected_zip_code': request.session.get('selected_zip_code'),
    }
    
    # Add global categories for navigation (available for all users)
    try:
        from catalog.models import Category
        context['global_categories'] = Category.objects.filter(
            is_active=True,
            parent=None
        ).prefetch_related('subcategories').order_by('sort_order', 'name')[:8]  # Limit to 8 main categories
    except:
        context['global_categories'] = []
    
    # Add cart and wishlist information for logged-in users
    if request.user.is_authenticated:
        try:
            # Import here to avoid circular imports
            from orders.models import Cart
            from accounts.models import Wishlist
            
            # Get all active carts for the user and only count those with items
            carts = Cart.objects.filter(user=request.user, is_active=True).prefetch_related('items')
            total_cart_items = sum(cart.total_items for cart in carts if cart.items.exists())
            context['total_cart_items'] = total_cart_items
            context['user_carts'] = [cart for cart in carts if cart.items.exists()]  # Only non-empty carts
            
            # Get wishlist count
            total_wishlist_items = Wishlist.objects.filter(user=request.user).count()
            context['total_wishlist_items'] = total_wishlist_items
            
            # Add user type information - superuser should be treated as customer when browsing
            is_admin = request.user.is_staff or request.user.is_superuser
            is_store_owner = getattr(request.user, 'user_type', None) == 'store_owner'
            is_delivery_agent = getattr(request.user, 'user_type', None) == 'delivery_agent'
            # Customer includes regular customers AND superusers acting as customers (unless specifically store_owner or delivery_agent)
            user_type = getattr(request.user, 'user_type', 'customer')
            is_customer = (user_type == 'customer' or request.user.is_superuser) and not (is_store_owner or is_delivery_agent)
            
            context['is_admin'] = is_admin
            context['is_store_owner'] = is_store_owner
            context['is_delivery_agent'] = is_delivery_agent
            context['is_customer'] = is_customer
            context['user_type'] = getattr(request.user, 'user_type', 'customer')
        except Exception as e:
            # Handle gracefully without logging to production
            context['total_cart_items'] = 0
            context['user_carts'] = []
            context['total_wishlist_items'] = 0
            context['is_admin'] = False
            context['is_store_owner'] = False
            context['is_delivery_agent'] = False
            context['is_customer'] = True
            context['user_type'] = 'customer'
    
    # Add available stores for the selected ZIP code
    selected_zip = request.session.get('selected_zip_code')
    if selected_zip:
        try:
            # Import here to avoid circular imports
            from locations.models import ZipArea
            from stores.models import Store
            
            zip_area = ZipArea.objects.get(zip_code=selected_zip, is_active=True)
            available_stores = Store.objects.filter(
                zip_coverage__zip_area=zip_area,
                is_active=True,
                status='open'
            ).distinct()
            context['available_stores'] = available_stores
            context['zip_area'] = zip_area
        except:
            context['available_stores'] = []
            context['zip_area'] = None
    else:
        context['available_stores'] = []
        context['zip_area'] = None
    
    return context


def admin_context(request):
    """Admin-specific context processor for dashboard statistics"""
    context = {}
    
    # Only add admin context for admin pages and superusers
    if request.path.startswith('/admin/') and request.user.is_authenticated and request.user.is_superuser:
        try:
            # Import models here to avoid circular imports
            from accounts.models import User
            from stores.models import Store
            from catalog.models import Product, Category
            from orders.models import Order
            from django.utils import timezone
            from datetime import timedelta
            
            # Get current counts
            context.update({
                'user_count': User.objects.count(),
                'store_count': Store.objects.filter(is_active=True).count(),
                'product_count': Product.objects.filter(is_active=True).count(),
                'category_count': Category.objects.filter(is_active=True).count(),
            })
            
            # Get today's statistics
            today = timezone.now().date()
            context.update({
                'orders_today': Order.objects.filter(created_at__date=today).count(),
                'orders_pending': Order.objects.filter(status='pending').count(),
                'orders_processing': Order.objects.filter(status='processing').count(),
                'orders_delivered_today': Order.objects.filter(
                    status='delivered',
                    updated_at__date=today
                ).count(),
            })
            
            # Get categories for dynamic navigation
            context['all_categories'] = Category.objects.filter(
                is_active=True,
                parent=None
            ).prefetch_related('subcategories').order_by('sort_order', 'name')
            
        except Exception as e:
            # Fallback to zero values if there's an error
            context.update({
                'user_count': 0,
                'store_count': 0, 
                'product_count': 0,
                'category_count': 0,
                'orders_today': 0,
                'orders_pending': 0,
                'orders_processing': 0,
                'orders_delivered_today': 0,
                'all_categories': [],
            })
    
    return context
