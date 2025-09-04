from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, F, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from orders.models import Order, Cart
from catalog.models import Product, Category, StoreProduct
from stores.models import Store, StoreZipCoverage
from locations.models import ZipArea

User = get_user_model()

class ModernAdminSite(admin.AdminSite):
    site_header = "🥩 Fresh Express Admin"
    site_title = "Admin Portal"
    index_title = "Management Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        # Remove custom dashboard URLs to use standard Django admin
        # Keep some enhanced views but redirect dashboard to admin index
        custom_urls = [
            path('dashboard/', self.admin_view(self.redirect_to_index), name='dashboard'),
            path('super-dashboard/', self.admin_view(self.super_dashboard_view), name='super_dashboard'),
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
            path('orders-management/', self.admin_view(self.orders_view), name='orders_management'),
            path('products-management/', self.admin_view(self.products_view), name='products_management'),
            path('users-management/', self.admin_view(self.users_view), name='users_management'),
            path('stores-management/', self.admin_view(self.stores_view), name='stores_management'),
            path('quick-actions/', self.admin_view(self.quick_actions_view), name='quick_actions'),
        ]
        return custom_urls + urls
    
    def redirect_to_index(self, request):
        """Redirect dashboard requests to admin index"""
        return redirect('admin:index')
    
    def super_dashboard_view(self, request):
        """Enhanced Super Admin Dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        try:
            # Enhanced statistics for super admin
            total_orders = Order.objects.count()
            total_users = User.objects.count()
            total_products = Product.objects.count()
            total_stores = Store.objects.filter(is_active=True).count()
            active_carts = Cart.objects.filter(is_active=True).count()
            total_categories = Category.objects.filter(is_active=True).count()
            total_zip_areas = ZipArea.objects.filter(is_active=True).count()
            
            # Revenue calculations
            weekly_orders = Order.objects.filter(created_at__date__gte=week_ago).count()
            monthly_orders = Order.objects.filter(created_at__date__gte=month_ago).count()
            
            weekly_revenue = Order.objects.filter(created_at__date__gte=week_ago).aggregate(
                total=Sum('total_amount'))['total'] or 0
            monthly_revenue = Order.objects.filter(created_at__date__gte=month_ago).aggregate(
                total=Sum('total_amount'))['total'] or 0
            
            # New users this week
            new_users_week = User.objects.filter(date_joined__date__gte=week_ago).count()
            
        except Exception as e:
            # Fallback values if queries fail
            total_orders = total_users = total_products = total_stores = 0
            active_carts = total_categories = total_zip_areas = 0
            weekly_orders = monthly_orders = new_users_week = 0
            weekly_revenue = monthly_revenue = 0
        
        context = {
            'title': 'Super Admin Dashboard',
            'total_orders': total_orders,
            'total_users': total_users,
            'total_products': total_products,
            'total_stores': total_stores,
            'active_carts': active_carts,
            'total_categories': total_categories,
            'total_zip_areas': total_zip_areas,
            'weekly_orders': weekly_orders,
            'monthly_orders': monthly_orders,
            'weekly_revenue': weekly_revenue,
            'monthly_revenue': monthly_revenue,
            'new_users_week': new_users_week,
        }
        
        return render(request, 'admin/overview_dashboard.html', context)
    
    
    def orders_view(self, request):
        orders = Order.objects.select_related('user').order_by('-created_at')[:50]
        context = {
            'title': 'Orders Management',
            'orders': orders,
        }
        return render(request, 'admin/orders_management.html', context)
    
    def products_view(self, request):
        products = Product.objects.select_related('category')[:50]
        categories = Category.objects.all()
        context = {
            'title': 'Products Management',
            'products': products,
            'categories': categories,
        }
        return render(request, 'admin/products_management.html', context)
    
    def users_view(self, request):
        try:
            UserModel = get_user_model()
            users = UserModel.objects.order_by('-date_joined')[:50]
        except Exception as e:
            users = []
            
        context = {
            'title': 'Users Management',
            'users': users,
            'section': 'users'
        }
        return render(request, 'admin/users_management.html', context)
    
    def analytics_view(self, request):
        """Advanced analytics view with comprehensive reporting"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Sales Analytics
        try:
            weekly_sales = Order.objects.filter(
                created_at__date__gte=week_ago,
                status='delivered'
            ).aggregate(
                total_sales=Sum('total_amount'),
                total_orders=Count('id')
            )
            
            monthly_sales = Order.objects.filter(
                created_at__date__gte=month_ago,
                status='delivered'
            ).aggregate(
                total_sales=Sum('total_amount'),
                total_orders=Count('id')
            )
            
            # Top selling products
            top_products = Product.objects.annotate(
                total_sold=Count('storeproduct__orderitem')
            ).order_by('-total_sold')[:10]
            
            # Store performance
            store_performance = Store.objects.annotate(
                total_orders=Count('storeproduct__orderitem__order'),
                total_revenue=Sum('storeproduct__orderitem__total_price')
            ).order_by('-total_revenue')[:10]
            
        except Exception as e:
            weekly_sales = monthly_sales = {'total_sales': 0, 'total_orders': 0}
            top_products = []
            store_performance = []
        
        context = {
            'title': 'Analytics & Reports',
            'section': 'analytics',
            'weekly_sales': weekly_sales,
            'monthly_sales': monthly_sales,
            'top_products': top_products,
            'store_performance': store_performance,
        }
        return render(request, 'admin/analytics.html', context)
    
    def stores_view(self, request):
        """Stores management view"""
        stores = Store.objects.annotate(
            coverage_areas=Count('storezipcoverage'),
            products_count=Count('storeproduct')
        ).order_by('-created_at')
        
        context = {
            'title': 'Stores Management',
            'stores': stores,
            'section': 'stores'
        }
        return render(request, 'admin/stores_management.html', context)
    
    def quick_actions_view(self, request):
        """Quick actions for common admin tasks"""
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'update_indian_stores':
                # Run the Indian stores update command
                from django.core.management import call_command
                try:
                    call_command('update_to_indian_stores')
                except Exception as e:
                    pass
            
            elif action == 'cleanup_sample_data':
                try:
                    call_command('cleanup_sample_data', '--confirm')
                except Exception as e:
                    pass
                    
            return redirect('admin:quick_actions')
        
        # Get current stats for the quick actions page
        context = {
            'title': 'Quick Actions',
            'section': 'quick_actions',
            'total_stores': Store.objects.count(),
            'total_products': Product.objects.count(),
            'total_users': User.objects.count(),
            'total_orders': Order.objects.count(),
            'total_categories': Category.objects.count(),
            'total_zip_areas': ZipArea.objects.count(),
        }
        return render(request, 'admin/quick_actions.html', context)

# Create custom admin site instance
admin_site = ModernAdminSite(name='modern_admin')

# Register models with custom admin site - minimal registration to avoid import errors
try:
    # Import most essential models only
    from accounts.models import User as CustomUser, UserProfile, OTPVerification
    from locations.models import Address, ZipArea  
    from catalog.models import Category, Product, StoreProduct
    from stores.models import Store, StoreZipCoverage
    from orders.models import Order, OrderItem, Cart, CartItem
    from payments.models import PaymentMethod, UPIProvider
    from delivery.models import DeliveryAgent, DeliveryAssignment
    from .models import Setting, SystemLog, FAQ, FAQCategory
    
    # Import admin classes
    from accounts.admin import UserAdmin as CustomUserAdmin, UserProfileAdmin, OTPVerificationAdmin
    from .admin import SettingAdmin, SystemLogAdmin, FAQAdmin, FAQCategoryAdmin
    
    # Register essential models with custom admin
    admin_site.register(CustomUser, CustomUserAdmin)
    admin_site.register(UserProfile, UserProfileAdmin)
    admin_site.register(OTPVerification, OTPVerificationAdmin)
    
    # Core CMS models
    admin_site.register(Setting, SettingAdmin)
    admin_site.register(SystemLog, SystemLogAdmin)
    admin_site.register(FAQ, FAQAdmin)
    admin_site.register(FAQCategory, FAQCategoryAdmin)
    
    # Core platform models
    admin_site.register(Category)
    admin_site.register(Product)
    admin_site.register(StoreProduct)
    admin_site.register(Store)
    admin_site.register(StoreZipCoverage)
    admin_site.register(Order)
    admin_site.register(OrderItem)
    admin_site.register(Cart)
    admin_site.register(CartItem)
    admin_site.register(ZipArea)
    admin_site.register(Address)
    admin_site.register(UPIProvider)
    admin_site.register(PaymentMethod)
    admin_site.register(DeliveryAgent)
    admin_site.register(DeliveryAssignment)
    
except Exception as e:
    # Continue silently if some imports fail
    pass
