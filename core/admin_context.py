from django.contrib import admin
from django.contrib.auth import get_user_model
from accounts.models import User
from stores.models import Store
from catalog.models import Product
from orders.models import Order
from django.utils import timezone
from datetime import datetime

def admin_stats(request):
    """
    Context processor to provide dashboard statistics for admin
    """
    if request.path.startswith('/admin/') and hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
        try:
            # Count statistics
            user_count = User.objects.count()
            store_count = Store.objects.filter(is_active=True).count()
            product_count = Product.objects.filter(is_active=True).count()
            
            # Orders today
            today = timezone.now().date()
            orders_today = Order.objects.filter(created_at__date=today).count()
            
            return {
                'user_count': user_count,
                'store_count': store_count,
                'product_count': product_count,
                'orders_today': orders_today,
            }
        except Exception as e:
            # Gracefully handle any database errors
            return {
                'user_count': 0,
                'store_count': 0,
                'product_count': 0,
                'orders_today': 0,
            }
    return {}
