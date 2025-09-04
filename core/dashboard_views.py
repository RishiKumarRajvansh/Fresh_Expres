"""
Unified Dashboard Views for all user types
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta
from .decorators import AdminRequiredMixin, StoreRequiredMixin, DeliveryAgentRequiredMixin

@login_required
def dashboard_router(request):
    """
    Route users to their appropriate dashboard based on user type
    """
    user = request.user
    user_type = getattr(user, 'user_type', 'customer')
    
    routing_map = {
        'admin': 'core:admin_dashboard',
        'store_owner': 'stores:dashboard',
        'store_staff': 'stores:dashboard', 
        'delivery_agent': 'delivery:agent_dashboard',
        'customer': 'core:customer_dashboard',
    }
    
    target_view = routing_map.get(user_type, 'core:customer_dashboard')
    return redirect(target_view)


class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    """Customer dashboard with orders, wishlist, etc."""
    template_name = 'dashboards/customer_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['customer']:
            return redirect('core:dashboard_router')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get recent orders
        from orders.models import Order
        recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
        
        # Get wishlist count
        wishlist_count = 0
        if hasattr(user, 'wishlists'):
            wishlist_count = user.wishlists.count()
        
        # Get loyalty points
        loyalty_points = 0
        if hasattr(user, 'loyalty_account'):
            loyalty_points = user.loyalty_account.available_points
        
        context.update({
            'recent_orders': recent_orders,
            'wishlist_count': wishlist_count,
            'loyalty_points': loyalty_points,
            'dashboard_title': f'Welcome back, {user.get_full_name() or user.username}!',
            'user_type': 'customer'
        })
        return context


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Admin dashboard with system overview"""
    template_name = 'dashboards/admin_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Import models
        from orders.models import Order
        from catalog.models import Product
        from stores.models import Store
        from accounts.models import User
        
        # Get statistics
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        try:
            stats = {
                'total_orders': Order.objects.count(),
                'weekly_orders': Order.objects.filter(created_at__date__gte=week_ago).count(),
                'total_products': Product.objects.count(),
                'total_stores': Store.objects.filter(is_active=True).count(),
                'total_users': User.objects.count(),
                'weekly_revenue': Order.objects.filter(
                    created_at__date__gte=week_ago,
                    status='delivered'
                ).aggregate(total=Sum('total_amount'))['total'] or 0,
            }
            
            # Recent orders
            recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]
            
            # Low stock alerts
            from catalog.models import StoreProduct
            low_stock_products = StoreProduct.objects.filter(
                stock_quantity__lt=10,
                is_available=True
            ).select_related('product', 'store')[:10]
            
        except Exception as e:
            stats = {
                'total_orders': 0, 'weekly_orders': 0,
                'total_products': 0, 'total_stores': 0,
                'total_users': 0, 'weekly_revenue': 0
            }
            recent_orders = []
            low_stock_products = []
        
        context.update({
            'stats': stats,
            'recent_orders': recent_orders,
            'low_stock_products': low_stock_products,
            'dashboard_title': 'Admin Dashboard - System Overview',
            'user_type': 'admin'
        })
        return context


class StoreDashboardView(StoreRequiredMixin, TemplateView):
    """Store owner/staff dashboard"""
    template_name = 'dashboards/store_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's store
        from stores.models import Store
        try:
            if user.user_type == 'store_owner':
                store = user.owned_stores.first()
            else:  # store_staff
                store = user.store_staff.first().store if hasattr(user, 'store_staff') else None
            
            if not store:
                return context
            
            # Store statistics
            from orders.models import Order
            from catalog.models import StoreProduct
            
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            
            store_stats = {
                'total_products': store.storeproduct_set.count(),
                'active_products': store.storeproduct_set.filter(is_available=True).count(),
                'total_orders': Order.objects.filter(
                    items__store_product__store=store
                ).distinct().count(),
                'weekly_orders': Order.objects.filter(
                    items__store_product__store=store,
                    created_at__date__gte=week_ago
                ).distinct().count(),
                'pending_orders': Order.objects.filter(
                    items__store_product__store=store,
                    status__in=['pending', 'confirmed']
                ).distinct().count(),
            }
            
            # Recent orders for this store
            recent_orders = Order.objects.filter(
                items__store_product__store=store
            ).distinct().order_by('-created_at')[:10]
            
            # Low stock products
            low_stock = store.storeproduct_set.filter(
                stock_quantity__lt=10,
                is_available=True
            )[:10]
            
        except Exception as e:
            store = None
            store_stats = {}
            recent_orders = []
            low_stock = []
        
        context.update({
            'store': store,
            'store_stats': store_stats,
            'recent_orders': recent_orders,
            'low_stock': low_stock,
            'dashboard_title': f'Store Dashboard - {store.name if store else "No Store"}',
            'user_type': user.user_type
        })
        return context


class DeliveryDashboardView(DeliveryAgentRequiredMixin, TemplateView):
    """Delivery agent dashboard"""
    template_name = 'dashboards/delivery_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get delivery agent profile
        from delivery.models import DeliveryAgent, DeliveryAssignment
        try:
            agent = DeliveryAgent.objects.get(user=user)
            
            # Agent statistics
            today = timezone.now().date()
            agent_stats = {
                'total_deliveries': agent.deliveryassignment_set.filter(
                    status='delivered'
                ).count(),
                'pending_deliveries': agent.deliveryassignment_set.filter(
                    status__in=['assigned', 'picked_up']
                ).count(),
                'today_deliveries': agent.deliveryassignment_set.filter(
                    assigned_at__date=today
                ).count(),
                'is_available': agent.is_available,
                'total_earnings': agent.deliveryassignment_set.filter(
                    status='delivered'
                ).count() * 50,  # Simplified calculation
            }
            
            # Current assignments
            current_assignments = agent.deliveryassignment_set.filter(
                status__in=['assigned', 'picked_up']
            ).order_by('-assigned_at')[:5]
            
            # Recent deliveries
            recent_deliveries = agent.deliveryassignment_set.filter(
                status='delivered'
            ).order_by('-delivered_at')[:10]
            
        except DeliveryAgent.DoesNotExist:
            agent = None
            agent_stats = {}
            current_assignments = []
            recent_deliveries = []
        
        context.update({
            'agent': agent,
            'agent_stats': agent_stats,
            'current_assignments': current_assignments,
            'recent_deliveries': recent_deliveries,
            'dashboard_title': 'Delivery Dashboard',
            'user_type': 'delivery_agent'
        })
        return context
