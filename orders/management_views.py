"""
Order Management Views

Enhanced views for comprehensive order management including:
- Order status updates
- Bulk operations
- Advanced filtering
- Status history tracking
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import json

from .models import Order, OrderStatusHistory
from .services import OrderStatusService, OrderWorkflowService, OrderAnalyticsService


class OrderManagementView(LoginRequiredMixin, ListView):
    """Enhanced order list view with filtering and management capabilities"""
    model = Order
    template_name = 'orders/order_management.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Order.objects.select_related('user', 'store', 'delivery_address')
        
        # Apply filters based on user role
        if hasattr(self.request.user, 'store'):
            # Store owner - only their orders
            queryset = queryset.filter(store=self.request.user.store)
        elif not self.request.user.is_staff:
            # Regular user - only their orders
            queryset = queryset.filter(user=self.request.user)
        # Admin users see all orders
        
        # Apply search filters
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        # Apply status filter
        status = self.request.GET.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply payment status filter
        payment_status = self.request.GET.get('payment_status', '').strip()
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        # Apply date range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['order_statuses'] = Order.ORDER_STATUS
        context['payment_statuses'] = Order.PAYMENT_STATUS
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
            'payment_status': self.request.GET.get('payment_status', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        
        # Add statistics
        if hasattr(self.request.user, 'store'):
            store = self.request.user.store
        else:
            store = None
        
        context['stats'] = OrderAnalyticsService.get_order_stats(store=store)
        
        return context


class OrderDetailManagementView(LoginRequiredMixin, DetailView):
    """Enhanced order detail view with management capabilities"""
    model = Order
    template_name = 'orders/order_detail_management.html'
    context_object_name = 'order'
    slug_field = 'order_number'
    slug_url_kwarg = 'order_number'
    
    def get_queryset(self):
        queryset = Order.objects.select_related('user', 'store', 'delivery_address')
        
        # Apply permissions based on user role
        if hasattr(self.request.user, 'store'):
            queryset = queryset.filter(store=self.request.user.store)
        elif not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Add status history
        context['status_history'] = order.status_history.select_related('updated_by').all()
        
        # Add possible next statuses
        context['next_statuses'] = OrderStatusService.get_next_possible_statuses(order.status)
        
        # Add management permissions
        context['can_update_status'] = (
            self.request.user.is_staff or 
            (hasattr(self.request.user, 'store') and self.request.user.store == order.store)
        )
        
        return context


@method_decorator(login_required, name='dispatch')
class OrderStatusUpdateView(View):
    """Handle order status updates via AJAX"""
    
    def post(self, request, order_number):
        try:
            # Get the order
            order = get_object_or_404(Order, order_number=order_number)
            
            # Check permissions
            if not request.user.is_staff:
                if hasattr(request.user, 'store'):
                    if request.user.store != order.store:
                        return JsonResponse({'success': False, 'message': 'Permission denied'})
                else:
                    return JsonResponse({'success': False, 'message': 'Permission denied'})
            
            # Get form data
            data = json.loads(request.body)
            new_status = data.get('status')
            notes = data.get('notes', '').strip()
            
            if not new_status:
                return JsonResponse({'success': False, 'message': 'Status is required'})
            
            # Update status
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
                    }
                })
            else:
                return JsonResponse({'success': False, 'message': message})
                
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@method_decorator(login_required, name='dispatch')
class BulkOrderActionsView(View):
    """Handle bulk order actions"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            action = data.get('action')
            order_ids = data.get('order_ids', [])
            
            if not action or not order_ids:
                return JsonResponse({'success': False, 'message': 'Action and order IDs are required'})
            
            # Get orders with permission check
            orders_queryset = Order.objects.filter(id__in=order_ids)
            if not request.user.is_staff:
                if hasattr(request.user, 'store'):
                    orders_queryset = orders_queryset.filter(store=request.user.store)
                else:
                    return JsonResponse({'success': False, 'message': 'Permission denied'})
            
            orders = list(orders_queryset)
            if not orders:
                return JsonResponse({'success': False, 'message': 'No valid orders found'})
            
            success_count = 0
            total_count = len(orders)
            
            if action == 'confirm':
                for order in orders:
                    if order.status == 'placed':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='confirmed',
                            updated_by=request.user,
                            notes='Bulk confirmation'
                        )
                        if success:
                            success_count += 1
            
            elif action == 'mark_preparing':
                for order in orders:
                    if order.status == 'confirmed':
                        success, _ = OrderStatusService.update_order_status(
                            order=order,
                            new_status='preparing',
                            updated_by=request.user,
                            notes='Bulk status update to preparing'
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
                            notes='Bulk status update to packed'
                        )
                        if success:
                            success_count += 1
            
            else:
                return JsonResponse({'success': False, 'message': 'Invalid action'})
            
            return JsonResponse({
                'success': True,
                'message': f'Updated {success_count} of {total_count} orders successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


@require_http_methods(["GET"])
@login_required
def order_analytics_api(request):
    """API endpoint for order analytics"""
    try:
        # Get date range from query parameters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Parse dates if provided
        if date_from:
            date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
        if date_to:
            date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
        
        # Get store context for store owners
        store = None
        if hasattr(request.user, 'store'):
            store = request.user.store
        
        # Get analytics data
        stats = OrderAnalyticsService.get_order_stats(
            store=store,
            date_from=date_from,
            date_to=date_to
        )
        
        return JsonResponse({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


class OrderDashboardView(LoginRequiredMixin, View):
    """Dashboard view for order management overview"""
    
    def get(self, request):
        context = {}
        
        # Get user context
        if hasattr(request.user, 'store'):
            store = request.user.store
            context['user_type'] = 'store_owner'
        else:
            store = None
            if request.user.is_staff:
                context['user_type'] = 'admin'
            else:
                context['user_type'] = 'customer'
        
        # Get pending orders (need attention)
        context['pending_orders'] = OrderStatusService.get_pending_orders(store=store)[:5]
        
        # Get recent orders
        recent_orders_query = Order.objects.select_related('user', 'store')
        if store:
            recent_orders_query = recent_orders_query.filter(store=store)
        elif not request.user.is_staff:
            recent_orders_query = recent_orders_query.filter(user=request.user)
        
        context['recent_orders'] = recent_orders_query.order_by('-created_at')[:10]
        
        # Get analytics for the dashboard
        context['analytics'] = OrderAnalyticsService.get_order_stats(store=store)
        
        # Get status counts for quick overview
        status_counts = {}
        for status_code, status_name in Order.ORDER_STATUS:
            count_query = Order.objects.filter(status=status_code)
            if store:
                count_query = count_query.filter(store=store)
            elif not request.user.is_staff:
                count_query = count_query.filter(user=request.user)
            
            status_counts[status_code] = {
                'name': status_name,
                'count': count_query.count()
            }
        
        context['status_counts'] = status_counts
        
        return render(request, 'orders/order_dashboard.html', context)
