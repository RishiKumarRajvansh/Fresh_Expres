"""
Store Owner Dashboard Views
Complete store management system with order notifications and delivery assignment
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta
import json

from .models import Store, StoreProduct
from orders.models import Order, OrderItem, Cart
from delivery.models import DeliveryAgent, DeliveryAssignment
from catalog.models import Product, Category
from accounts.models import User


@login_required
def store_dashboard(request):
    """Main store dashboard with real-time order notifications"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get dashboard statistics
    today = timezone.now().date()
    
    # Today's orders
    todays_orders = Order.objects.filter(
        store=store,
        created_at__date=today
    ).exclude(status='cancelled')
    
    # Pending orders (needs immediate attention)
    pending_orders = Order.objects.filter(
        store=store,
        status__in=['pending', 'confirmed']
    ).order_by('-created_at')
    
    # Recent orders (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_orders = Order.objects.filter(
        store=store,
        created_at__date__gte=week_ago
    ).order_by('-created_at')[:10]
    
    # Low stock products
    low_stock_products = StoreProduct.objects.filter(
        store=store,
        stock_quantity__lte=10,
        is_available=True
    ).order_by('stock_quantity')[:10]
    
    # Available delivery agents
    available_agents = DeliveryAgent.objects.filter(
        store=store,
        is_available=True,
        user__is_active=True
    )
    
    # Dashboard stats
    stats = {
        'todays_orders': todays_orders.count(),
        'pending_orders': pending_orders.count(),
        'todays_revenue': todays_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
        'total_products': StoreProduct.objects.filter(store=store).count(),
        'active_products': StoreProduct.objects.filter(
            store=store, is_available=True
        ).count(),
        'low_stock_count': low_stock_products.count(),
        'available_agents': available_agents.count(),
    }
    
    context = {
        'store': store,
        'stats': stats,
        'pending_orders': pending_orders[:5],  # Show only first 5
        'recent_orders': recent_orders,
        'low_stock_products': low_stock_products,
        'available_agents': available_agents,
        'todays_orders': todays_orders[:10],
    }
    
    return render(request, 'stores/dashboard_enhanced.html', context)


@login_required
def store_orders(request):
    """Store orders management with filtering and status updates"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Filter parameters
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    orders = Order.objects.filter(store=store).select_related(
        'user', 'delivery_assignment__delivery_agent__user'
    ).prefetch_related('items__store_product__product')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if date_filter:
        if date_filter == 'today':
            orders = orders.filter(created_at__date=timezone.now().date())
        elif date_filter == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            orders = orders.filter(created_at__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            orders = orders.filter(created_at__gte=month_ago)
    
    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Order by creation time (newest first)
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_orders = paginator.get_page(page_number)
    
    # Status choices for filter
    status_choices = Order.STATUS_CHOICES
    
    context = {
        'store': store,
        'orders': page_orders,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'status_choices': status_choices,
    }
    
    return render(request, 'stores/orders_management.html', context)


@login_required
@require_POST
def update_order_status(request):
    """Update order status and assign delivery agent"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    order_id = request.POST.get('order_id')
    new_status = request.POST.get('status')
    agent_id = request.POST.get('agent_id')
    
    try:
        order = Order.objects.get(id=order_id, store=store)
        
        # Validate status transition
        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['preparing', 'cancelled'],
            'preparing': ['ready_for_pickup', 'cancelled'],
            'ready_for_pickup': ['out_for_delivery'],
            'out_for_delivery': ['delivered'],
        }
        
        if order.status not in valid_transitions:
            return JsonResponse({
                'success': False, 
                'message': f'Cannot update order in {order.status} status'
            })
        
        if new_status not in valid_transitions[order.status]:
            return JsonResponse({
                'success': False, 
                'message': f'Invalid status transition from {order.status} to {new_status}'
            })
        
        # Update order status
        order.status = new_status
        order.save()
        
        # Assign delivery agent if provided and status is ready for pickup
        if agent_id and new_status in ['ready_for_pickup', 'out_for_delivery']:
            try:
                agent = DeliveryAgent.objects.get(id=agent_id, store=store)
                
                # Create or update delivery assignment
                assignment, created = DeliveryAssignment.objects.get_or_create(
                    order=order,
                    defaults={
                        'delivery_agent': agent,
                        'status': 'assigned',
                        'assigned_at': timezone.now(),
                    }
                )
                
                if not created:
                    assignment.delivery_agent = agent
                    assignment.status = 'assigned'
                    assignment.assigned_at = timezone.now()
                    assignment.save()
                
                # Update agent availability
                agent.current_orders_count = DeliveryAssignment.objects.filter(
                    delivery_agent=agent,
                    status__in=['assigned', 'accepted', 'picked_up']
                ).count()
                agent.save()
                
            except DeliveryAgent.DoesNotExist:
                return JsonResponse({
                    'success': False, 
                    'message': 'Invalid delivery agent selected'
                })
        
        # Send real-time notification to customer (via WebSocket)
        # This would integrate with the WebSocket consumers we have
        
        return JsonResponse({
            'success': True, 
            'message': f'Order status updated to {new_status}',
            'new_status': order.get_status_display(),
            'order_id': order.id
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def order_detail(request, order_id):
    """Detailed order view for store owners"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
        order = Order.objects.select_related(
            'user', 'delivery_assignment__delivery_agent__user'
        ).prefetch_related(
            'items__store_product__product'
        ).get(id=order_id, store=store)
    except (Store.DoesNotExist, Order.DoesNotExist):
        return redirect('stores:dashboard')
    
    # Available delivery agents
    available_agents = DeliveryAgent.objects.filter(
        store=store,
        is_available=True,
        user__is_active=True
    )
    
    context = {
        'store': store,
        'order': order,
        'available_agents': available_agents,
        'status_choices': Order.STATUS_CHOICES,
    }
    
    return render(request, 'stores/order_detail.html', context)


@login_required
def inventory_management(request):
    """Store inventory management"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Filter parameters
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    products = StoreProduct.objects.filter(store=store).select_related(
        'product', 'product__category'
    )
    
    # Apply filters
    if category_filter:
        products = products.filter(product__category_id=category_filter)
    
    if stock_filter:
        if stock_filter == 'low':
            products = products.filter(stock_quantity__lte=10)
        elif stock_filter == 'out':
            products = products.filter(stock_quantity=0)
        elif stock_filter == 'available':
            products = products.filter(stock_quantity__gt=0, is_available=True)
    
    if search_query:
        products = products.filter(
            Q(product__name__icontains=search_query) |
            Q(product__description__icontains=search_query)
        )
    
    # Order by stock quantity (lowest first for attention)
    products = products.order_by('stock_quantity', 'product__name')
    
    # Pagination
    paginator = Paginator(products, 25)
    page_number = request.GET.get('page')
    page_products = paginator.get_page(page_number)
    
    # Categories for filter
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    context = {
        'store': store,
        'products': page_products,
        'categories': categories,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'search_query': search_query,
    }
    
    return render(request, 'stores/inventory_management.html', context)


@login_required
@require_POST
def update_stock(request):
    """Update product stock quantity"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    product_id = request.POST.get('product_id')
    new_quantity = request.POST.get('quantity')
    
    try:
        new_quantity = int(new_quantity)
        if new_quantity < 0:
            return JsonResponse({'success': False, 'message': 'Quantity cannot be negative'})
        
        store_product = StoreProduct.objects.get(id=product_id, store=store)
        old_quantity = store_product.stock_quantity
        
        store_product.stock_quantity = new_quantity
        store_product.last_stock_update = timezone.now()
        
        # Auto-disable if out of stock
        if new_quantity == 0:
            store_product.is_available = False
        elif old_quantity == 0 and new_quantity > 0:
            store_product.is_available = True
        
        store_product.save()
        
        # Use the inventory sync service if available
        try:
            from catalog.services_inventory import InventorySyncService
            InventorySyncService.update_stock(
                store=store,
                product=store_product.product,
                new_quantity=new_quantity,
                reason="Manual update by store owner",
                user=request.user
            )
        except ImportError:
            pass  # Service not available, continue with basic update
        
        return JsonResponse({
            'success': True, 
            'message': f'Stock updated from {old_quantity} to {new_quantity}',
            'new_quantity': new_quantity,
            'is_available': store_product.is_available
        })
        
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid quantity value'})
    except StoreProduct.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def delivery_agents_management(request):
    """Manage delivery agents for the store"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    agents = DeliveryAgent.objects.filter(store=store).select_related(
        'user'
    ).annotate(
        active_orders=Count('assignments', 
                          filter=Q(assignments__status__in=['assigned', 'accepted', 'picked_up']))
    ).order_by('user__first_name')
    
    context = {
        'store': store,
        'agents': agents,
    }
    
    return render(request, 'stores/agents_management.html', context)


@login_required
@csrf_exempt
def get_new_orders_count(request):
    """AJAX endpoint to get new orders count for real-time updates"""
    try:
        store = Store.objects.get(owner=request.user, is_active=True)
        new_orders_count = Order.objects.filter(
            store=store,
            status='pending',
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        pending_orders_count = Order.objects.filter(
            store=store,
            status__in=['pending', 'confirmed']
        ).count()
        
        return JsonResponse({
            'success': True,
            'new_orders': new_orders_count,
            'pending_orders': pending_orders_count,
            'timestamp': timezone.now().isoformat()
        })
    except Store.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Access denied'})


# Auto-assignment logic for delivery agents
def auto_assign_delivery_agent(order):
    """Auto-assign the best available delivery agent to an order"""
    try:
        # Find available agents for the store
        available_agents = DeliveryAgent.objects.filter(
            store=order.store,
            is_available=True,
            user__is_active=True
        ).annotate(
            active_orders_count=Count('assignments', 
                                    filter=Q(assignments__status__in=['assigned', 'accepted', 'picked_up']))
        ).order_by('active_orders_count', 'id')  # Assign to agent with least active orders
        
        if available_agents.exists():
            best_agent = available_agents.first()
            
            # Create delivery assignment
            assignment = DeliveryAssignment.objects.create(
                order=order,
                delivery_agent=best_agent,
                status='assigned',
                assigned_at=timezone.now()
            )
            
            # Update agent's current order count
            best_agent.current_orders_count = available_agents.filter(
                id=best_agent.id
            ).first().active_orders_count + 1
            best_agent.save()
            
            return assignment
        
    except Exception as e:
        pass  # Silently handle errors
    
    return None
