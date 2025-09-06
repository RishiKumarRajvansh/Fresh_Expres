"""
Store Manager Order Management Views

Enhanced order management system specifically designed for store managers including:
- Real-time order dashboard
- Order status management with workflow
- Bulk operations for efficiency  
- Order analytics and reporting
- Integration with delivery management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, View
from django.contrib import messages
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import Store
from orders.models import Order, OrderStatusHistory
from orders.services import OrderStatusService, OrderWorkflowService, OrderAnalyticsService
from core.decorators import store_required, StoreRequiredMixin


class StoreOrderDashboardView(StoreRequiredMixin, TemplateView):
    """Enhanced store order dashboard with real-time updates - Store Owner Only"""
    template_name = 'stores/orders/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the store for the current user (owners only)
        try:
            store = Store.objects.get(owner=self.request.user)
        except Store.DoesNotExist:
            messages.error(self.request, 'No store found for your account.')
            return context
        
        context['store'] = store
        
        # Get order statistics for today
        today = timezone.now().date()
        today_orders = Order.objects.filter(store=store, created_at__date=today)
        
        context['today_stats'] = {
            'total_orders': today_orders.count(),
            'pending_orders': today_orders.filter(status__in=['placed', 'confirmed']).count(),
            'preparing_orders': today_orders.filter(status='preparing').count(),
            'ready_orders': today_orders.filter(status__in=['packed', 'ready_for_pickup']).count(),
            'completed_orders': today_orders.filter(status='delivered').count(),
            'revenue': today_orders.filter(status='delivered').aggregate(
                total=Sum('total_amount'))['total'] or 0
        }
        
        # Get pending orders that need immediate attention
        pending_orders = Order.objects.filter(
            store=store,
            status__in=['placed', 'confirmed', 'preparing']
        ).order_by('created_at')[:10]
        
        context['pending_orders'] = pending_orders
        
        # Get orders by status for quick overview
        status_counts = {}
        for status_code, status_name in Order.ORDER_STATUS:
            count = Order.objects.filter(store=store, status=status_code).count()
            status_counts[status_code] = {
                'name': status_name,
                'count': count
            }
        
        context['status_counts'] = status_counts
        
        # Get recent order activity
        recent_orders = Order.objects.filter(store=store).order_by('-created_at')[:5]
        context['recent_orders'] = recent_orders
        
        # Get weekly analytics
        week_ago = timezone.now() - timedelta(days=7)
        context['weekly_analytics'] = OrderAnalyticsService.get_order_stats(
            store=store,
            date_from=week_ago.date()
        )
        
        return context


class StoreOrderListView(StoreRequiredMixin, ListView):
    """Enhanced store order list with advanced filtering - Store Owner Only"""
    model = Order
    template_name = 'stores/orders/list.html'
    context_object_name = 'orders'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user is authenticated
        if not request.user.is_authenticated:
            return redirect('accounts:email_login')
            
        # Only allow store owners, not staff
        if hasattr(request.user, 'user_type') and request.user.user_type == 'store_staff':
            messages.error(request, 'Staff members can only view orders assigned to them. Please use the staff orders page.')
            return redirect('stores:staff_orders')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Get the store for the current user (owners only)
        try:
            store = Store.objects.get(owner=self.request.user)
        except Store.DoesNotExist:
            return Order.objects.none()
        
        queryset = Order.objects.filter(store=store).select_related(
            'user', 'delivery_address'
        ).prefetch_related('items__store_product__product')
        
        # Apply filters
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        payment_status_filter = self.request.GET.get('payment_status', '').strip()
        if payment_status_filter:
            queryset = queryset.filter(payment_status=payment_status_filter)
        
        date_filter = self.request.GET.get('date', '').strip()
        if date_filter == 'today':
            queryset = queryset.filter(created_at__date=timezone.now().date())
        elif date_filter == 'yesterday':
            yesterday = timezone.now().date() - timedelta(days=1)
            queryset = queryset.filter(created_at__date=yesterday)
        elif date_filter == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(created_at__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            queryset = queryset.filter(created_at__gte=month_ago)
        
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__phone__icontains=search)
            )
        
        # Sort orders
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by in ['-created_at', 'created_at', '-total_amount', 'total_amount', 'status']:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get store
        try:
            store = Store.objects.get(owner=self.request.user)
        except Store.DoesNotExist:
            store = Store.objects.get(owner=self.request.user)
        
        context['store'] = store
        context['order_statuses'] = Order.ORDER_STATUS
        context['payment_statuses'] = Order.PAYMENT_STATUS
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'payment_status': self.request.GET.get('payment_status', ''),
            'date': self.request.GET.get('date', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', '-created_at'),
        }
        
        return context


class StoreOrderDetailView(StoreRequiredMixin, DetailView):
    """Enhanced store order detail with management capabilities - Store Owner Only"""
    model = Order
    template_name = 'stores/orders/detail.html'
    context_object_name = 'order'
    slug_field = 'order_number'
    slug_url_kwarg = 'order_number'
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow store owners, not staff
        if request.user.user_type == 'store_staff':
            # Redirect to staff order detail instead
            return redirect('stores:staff_order_detail', order_number=kwargs['order_number'])
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Limit to orders from the user's store (owners only)
        try:
            store = Store.objects.get(owner=self.request.user)
        except Store.DoesNotExist:
            return Order.objects.none()
        
        return Order.objects.filter(store=store).select_related(
            'user', 'store', 'delivery_address'
        ).prefetch_related('items__store_product__product', 'status_history__updated_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Get store
        context['store'] = order.store
        
        # Add status history
        context['status_history'] = order.status_history.select_related('updated_by').all()
        
        # Add possible next statuses based on current status
        context['next_statuses'] = OrderStatusService.get_next_possible_statuses(order.status)
        
        # Add order items with pricing details
        context['order_items'] = order.items.select_related('store_product__product').all()
        
        # Calculate additional metrics
        context['order_metrics'] = {
            'total_items': sum(item.quantity for item in context['order_items']),
            'preparation_time': self._calculate_preparation_time(order),
            'order_age': (timezone.now() - order.created_at).total_seconds() / 3600,  # hours
        }
        
        # Add delivery information if available
        if hasattr(order, 'delivery_assignment'):
            context['delivery_info'] = order.delivery_assignment
        
        # Add cancellation permission based on current user
        context['can_cancel_order'] = order.can_be_cancelled(self.request.user)
        
        return context
    
    def _calculate_preparation_time(self, order):
        """Calculate estimated preparation time based on order items"""
        # This could be enhanced with actual preparation time data
        base_time = 15  # Base 15 minutes
        item_time = sum(item.quantity for item in order.items.all()) * 2  # 2 minutes per item
        return base_time + item_time


@method_decorator(login_required, name='dispatch')  
@method_decorator(store_required, name='dispatch')
class StoreOrderStatusUpdateView(View):
    """Handle order status updates for store managers"""
    
    def post(self, request, order_number):
        try:
            # Get the store for the current user
            try:
                store = Store.objects.get(owner=request.user)
            except Store.DoesNotExist:
                store = Store.objects.get(owner=request.user)
                if not store:
                    return JsonResponse({'success': False, 'message': 'Store not found'})
            
            # Get the order
            order = get_object_or_404(Order, order_number=order_number, store=store)
            
            # Get form data
            data = json.loads(request.body)
            new_status = data.get('status')
            notes = data.get('notes', '').strip()
            
            if not new_status:
                return JsonResponse({'success': False, 'message': 'Status is required'})
            
            # Update status using our service
            success, message = OrderStatusService.update_order_status(
                order=order,
                new_status=new_status,
                updated_by=request.user,
                notes=notes if notes else None
            )
            
            if success:
                # Get updated order data
                order.refresh_from_db()
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'order': {
                        'status': order.status,
                        'status_display': order.get_status_display(),
                        'payment_status': order.payment_status,
                        'payment_status_display': order.get_payment_status_display(),
                        'updated_at': order.updated_at.isoformat(),
                    }
                })
            else:
                return JsonResponse({'success': False, 'message': message})
                
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@method_decorator(login_required, name='dispatch')
@method_decorator(store_required, name='dispatch') 
class StoreBulkOrderActionsView(View):
    """Handle bulk order actions for store managers"""
    
    def post(self, request):
        try:
            # Get the store for the current user
            try:
                store = Store.objects.get(owner=request.user)
            except Store.DoesNotExist:
                store = Store.objects.get(owner=request.user)
                if not store:
                    return JsonResponse({'success': False, 'message': 'Store not found'})
            
            data = json.loads(request.body)
            action = data.get('action')
            order_ids = data.get('order_ids', [])
            
            if not action or not order_ids:
                return JsonResponse({'success': False, 'message': 'Action and order IDs are required'})
            
            # Get orders for this store only
            orders = Order.objects.filter(id__in=order_ids, store=store)
            
            if not orders.exists():
                return JsonResponse({'success': False, 'message': 'No valid orders found'})
            
            success_count = 0
            total_count = orders.count()
            
            # Handle different bulk actions
            if action == 'confirm_orders':
                for order in orders:
                    if order.status == 'placed':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='confirmed',
                            updated_by=request.user,
                            notes='Bulk confirmation by store'
                        )
                        if success:
                            success_count += 1
            
            elif action == 'start_preparing':
                for order in orders:
                    if order.status == 'confirmed':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='preparing',
                            updated_by=request.user,
                            notes='Bulk status update - started preparing'
                        )
                        if success:
                            success_count += 1
            
            elif action == 'mark_packed':
                for order in orders:
                    if order.status == 'preparing':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='packed',
                            updated_by=request.user,
                            notes='Bulk status update - marked as packed'
                        )
                        if success:
                            success_count += 1
            
            elif action == 'mark_ready':
                for order in orders:
                    if order.status == 'packed':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='ready_for_pickup',
                            updated_by=request.user,
                            notes='Bulk status update - ready for pickup'
                        )
                        if success:
                            success_count += 1
            
            else:
                return JsonResponse({'success': False, 'message': 'Invalid action'})
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully updated {success_count} of {total_count} orders'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@login_required
@store_required
def store_order_analytics_api(request):
    """API endpoint for store order analytics"""
    try:
        # Get the store for the current user
        try:
            store = Store.objects.get(owner=request.user)
        except Store.DoesNotExist:
            store = Store.objects.get(owner=request.user)
            if not store:
                return JsonResponse({'success': False, 'message': 'Store not found'})
        
        # Get date range from query parameters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Parse dates if provided
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Get analytics data for the store
        stats = OrderAnalyticsService.get_order_stats(
            store=store,
            date_from=date_from,
            date_to=date_to
        )
        
        # Add store-specific metrics
        orders_query = Order.objects.filter(store=store)
        if date_from:
            orders_query = orders_query.filter(created_at__gte=date_from)
        if date_to:
            orders_query = orders_query.filter(created_at__lte=date_to)
        
        stats['store_metrics'] = {
            'avg_preparation_time': 25,  # Could be calculated from actual data
            'customer_satisfaction': 4.2,  # Could be from ratings
            'repeat_customer_rate': 65,  # Could be calculated
        }
        
        return JsonResponse({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
