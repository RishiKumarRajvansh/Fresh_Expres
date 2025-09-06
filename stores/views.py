from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from .models import Store, StoreClosureRequest
from catalog.models import StoreProduct
from orders.models import Order
from delivery_new.models import DeliveryAgent
from core.decorators import StoreRequiredMixin, store_required
import json

# Note: We don't show store lists to users anymore (Blinkit-style automatic selection)
# These views are mainly for store owners to manage their stores

class StoreDashboardView(StoreRequiredMixin, TemplateView):
    """Store owner dashboard - Only accessible by store owners and staff"""
    template_name = 'stores/dashboard_enhanced.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get stores owned by current user
        user_stores = Store.objects.filter(owner=self.request.user)
        
        if user_stores.exists():
            # For now, get the first store (can be enhanced for multi-store owners)
            store = user_stores.first()
            context['store'] = store
            
            # Get today's date for filtering
            today = timezone.now().date()
            
            # Get comprehensive stats
            total_products = StoreProduct.objects.filter(store=store).count()
            active_products = StoreProduct.objects.filter(store=store, is_available=True).count()
            
            # Get pending orders for dashboard
            try:
                from orders.models import Order
                from django.db.models import Sum
                
                # Today's orders
                today_orders = Order.objects.filter(
                    store=store,
                    created_at__date=today
                ).exclude(status='cancelled')
                
                # Pending orders
                pending_orders = Order.objects.filter(
                    store=store,
                    status__in=['pending', 'confirmed']
                ).select_related('user').order_by('-created_at')[:10]
                
                # Recent orders (last 5)
                recent_orders = Order.objects.filter(
                    store=store
                ).select_related('user').order_by('-created_at')[:5]
                
                # Revenue calculations
                today_revenue = today_orders.aggregate(
                    total=Sum('total_amount')
                )['total'] or 0
                
                # Low stock items
                low_stock_products = StoreProduct.objects.filter(
                    store=store,
                    stock_quantity__lte=10,
                    is_available=True
                ).select_related('product')[:10]
                
                context.update({
                    'pending_orders': pending_orders,
                    'recent_orders': recent_orders,
                    'low_stock_products': low_stock_products,
                    'today_orders_count': today_orders.count(),
                    'today_revenue': today_revenue,
                    'pending_orders_count': pending_orders.count(),
                    'low_stock_count': low_stock_products.count(),
                })
                
            except Exception as e:
                context.update({
                    'pending_orders': [],
                    'recent_orders': [],
                    'low_stock_products': [],
                    'today_orders_count': 0,
                    'today_revenue': 0,
                    'pending_orders_count': 0,
                    'low_stock_count': 0,
                })
            
            # Get basic stats
            context['total_products'] = total_products
            context['active_products'] = active_products
            
            # Stats for the enhanced dashboard
            # Determine available delivery agents for this store: either assigned to the store
            # or those who serve any of the store's active ZIP areas.
            agents_qs = DeliveryAgent.objects.filter(
                store=store,
                is_available=True
            ).distinct()

            # If the store is closed, we shouldn't show pending orders or available agents
            if store.status != 'open':
                available_agents_count = 0
            else:
                available_agents_count = agents_qs.count()

            context['stats'] = {
                'pending_orders': context.get('pending_orders_count', 0),
                'low_stock_count': context.get('low_stock_count', 0),
                'available_agents': available_agents_count,
                'today_orders': context.get('today_orders_count', 0),
                'today_revenue': context.get('today_revenue', 0),
                'total_products': total_products,
                'active_products': active_products,
            }
            
            # Store status
            context['store_status'] = store.status
            context['is_store_open'] = store.is_open
            # Provide agents queryset and a simple list for templates
            context['available_agents_qs'] = agents_qs if store.status == 'open' else DeliveryAgent.objects.none()
            context['available_agents'] = list(agents_qs) if store.status == 'open' else []
            
        return context

class StoreProfileView(LoginRequiredMixin, TemplateView):
    """Store profile management"""
    template_name = 'stores/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class StoreProductsView(LoginRequiredMixin, ListView):
    """Manage store products"""
    template_name = 'stores/products.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            return StoreProduct.objects.filter(store=store).select_related('product')
        return StoreProduct.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class StoreOrdersView(StoreRequiredMixin, ListView):
    """View and manage store orders"""
    template_name = 'stores/orders.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        # StoreRequiredMixin already ensures the user is authenticated and a store owner
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            # Return orders for this store (will be implemented with Order model)
            from orders.models import Order
            return Order.objects.filter(store=store).order_by('-created_at')
        return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class DeliveryAgentsView(LoginRequiredMixin, ListView):
    """Manage delivery agents"""
    template_name = 'stores/delivery_agents.html'
    context_object_name = 'agents'
    
    def get_queryset(self):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            # If the store is closed, return no agents
            if store.status != 'open':
                return DeliveryAgent.objects.none()

            # Return delivery agents assigned to the store or who serve the store's active ZIP areas
            agents_qs = DeliveryAgent.objects.filter(
                store=store,
                status='active'
            ).distinct().order_by('-is_available', 'user__last_name')

            return agents_qs
        return []

class ClosureRequestView(LoginRequiredMixin, FormView):
    """Request store closure"""
    template_name = 'stores/closure_request.html'
    success_url = reverse_lazy('stores:dashboard')
    
    def form_valid(self, form):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            
            # Create closure request (simplified)
            StoreClosureRequest.objects.create(
                store=store,
                requested_by=self.request.user,
                reason=form.cleaned_data.get('reason', 'Emergency closure'),
                requested_until=form.cleaned_data.get('requested_until')
            )
        
        return super().form_valid(form)

# API Views for store management
class StoreStatusAPIView(LoginRequiredMixin, TemplateView):
    """API to check store status"""
    
    def get(self, request, *args, **kwargs):
        user_stores = Store.objects.filter(owner=request.user)
        
        if not user_stores.exists():
            return JsonResponse({'error': 'No store found'})
        
        store = user_stores.first()
        
        return JsonResponse({
            'store_id': store.id,
            'store_name': store.name,
            'status': store.status,
            'is_open': store.is_open,
            'total_products': StoreProduct.objects.filter(store=store).count(),
        })

class ToggleProductAPIView(LoginRequiredMixin, TemplateView):
    """API to toggle product availability"""
    
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        
        user_stores = Store.objects.filter(owner=request.user)
        if not user_stores.exists():
            return JsonResponse({'error': 'No store found'})
        
        store = user_stores.first()
        
        try:
            store_product = StoreProduct.objects.get(id=product_id, store=store)
            store_product.is_available = not store_product.is_available
            store_product.save()
            
            return JsonResponse({
                'success': True,
                'is_available': store_product.is_available,
                'message': f'Product {"enabled" if store_product.is_available else "disabled"}'
            })
        except StoreProduct.DoesNotExist:
            return JsonResponse({'error': 'Product not found'})

class StoreAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'stores/analytics.html'

class AddProductView(LoginRequiredMixin, FormView):
    template_name = 'stores/add_product.html'
    success_url = reverse_lazy('stores:products')

class EditProductView(LoginRequiredMixin, FormView):
    template_name = 'stores/edit_product.html'
    success_url = reverse_lazy('stores:products')

class BulkUploadView(LoginRequiredMixin, FormView):
    template_name = 'stores/bulk_upload.html'
    success_url = reverse_lazy('stores:products')

class OrderDetailView(LoginRequiredMixin, StoreRequiredMixin, TemplateView):
    template_name = 'stores/order_detail.html'

class UpdateOrderStatusView(LoginRequiredMixin, StoreRequiredMixin, TemplateView):
    template_name = 'stores/update_order_status.html'

class CheckAvailabilityView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'available': True})

class UpdateInventoryView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})


# ================ NEW STORE DASHBOARD VIEWS ================

@store_required
def store_orders(request):
    """View for managing store orders - Only accessible by store owners"""
    # Get the store owned by current user
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            return render(request, 'stores/access_denied.html')
    except Store.DoesNotExist:
        return render(request, 'stores/access_denied.html')
    
    # Get orders for this store
    status_filter = request.GET.get('status', '')
    orders = Order.objects.filter(store=store)
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    orders = orders.order_by('-created_at')
    
    context = {
        'store': store,
        'orders': orders,
        'status_filter': status_filter,
        'order_statuses': Order._meta.get_field('status').choices,
    }
    
    return render(request, 'stores/orders_management.html', context)


@store_required
def order_detail(request, order_id):
    """View order details - Only accessible by store owners and staff"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            return render(request, 'stores/access_denied.html')
        
        order = get_object_or_404(Order, id=order_id, store=store)
    except Store.DoesNotExist:
        return render(request, 'stores/access_denied.html')
    
    # Staff assignment and assignment features removed
    order.staff_assignment = None
    
    # Get the latest delivery for this order
    try:
        from delivery_new.models import Delivery
        delivery = Delivery.objects.filter(order=order).latest('assigned_at')
    except:
        delivery = None
    
    context = {
        'store': store,
        'order': order,
        'delivery': delivery,
        'available_staff': [],  # Staff functionality removed
    }
    
    return render(request, 'stores/order_detail.html', context)


@store_required
def store_inventory(request):
    """View and manage store inventory - Only accessible by store owners"""
    try:
        store = Store.objects.get(owner=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Handle POST request for adding new products
    if request.method == 'POST':
        try:
            from catalog.models import Product, Category, ProductImage
            
            # Get or create the base product
            product_name = request.POST.get('product_name')
            description = request.POST.get('description', '')
            category_id = request.POST.get('category')
            
            # Get the category object
            try:
                category = Category.objects.get(id=category_id, is_active=True)
            except Category.DoesNotExist:
                messages.error(request, 'Please select a valid category.')
                return redirect('stores:inventory_management')
            
            # Handle images
            images = request.FILES.getlist('images')
            if not images:
                messages.error(request, 'Please upload at least one product image.')
                return redirect('stores:inventory_management')
            
            if len(images) > 5:
                messages.error(request, 'You can upload maximum 5 images.')
                return redirect('stores:inventory_management')
            
            # Create the product with the first image as main image
            product, created = Product.objects.get_or_create(
                name=product_name,
                category=category,
                defaults={
                    'description': description,
                    'brand': store.name,
                    'slug': product_name.lower().replace(' ', '-').replace('/', '-'),
                    'weight_per_unit': float(request.POST.get('weight_per_unit', 1000)),
                    'unit_type': request.POST.get('unit_type', 'grams'),
                    'nutritional_info': {},
                    'image': images[0],  # First image as main image
                }
            )
            
            # If product already exists, update the main image
            if not created:
                product.image = images[0]
                product.description = description
                product.save()
            
            # Add additional images (if any)
            if len(images) > 1:
                # Clear existing additional images for this product
                ProductImage.objects.filter(product=product).delete()
                
                for i, image in enumerate(images[1:], 1):  # Skip first image
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        sort_order=i,
                        is_active=True
                    )
            
            # Create or update store product
            store_product, created = StoreProduct.objects.get_or_create(
                store=store,
                product=product,
                defaults={
                    'price': float(request.POST.get('price', 0)),
                    'stock_quantity': int(request.POST.get('stock_quantity', 0)),
                    'is_available': request.POST.get('is_available') == 'on',
                }
            )
            
            if not created:
                # Update existing product
                store_product.price = float(request.POST.get('price', 0))
                store_product.stock_quantity = int(request.POST.get('stock_quantity', 0))
                store_product.is_available = request.POST.get('is_available') == 'on'
                store_product.save()
            
            messages.success(request, f'Product "{product_name}" added successfully!')
            return redirect('stores:inventory_management')
            
        except Exception as e:
            messages.error(request, f'Failed to add product: {str(e)}')
            return redirect('stores:inventory_management')
    
    # Get products for this store
    products = StoreProduct.objects.filter(store=store).select_related('product')
    
    # Filter by stock level
    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'low':
        products = products.filter(stock_quantity__lt=10)
    elif stock_filter == 'out':
        products = products.filter(stock_quantity=0)
    
    # Get categories for the form
    from catalog.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = {
        'store': store,
        'products': products,
        'stock_filter': stock_filter,
        'categories': categories,
    }
    
    return render(request, 'stores/inventory_management.html', context)


@store_required
def edit_store_product(request, product_id):
    """Edit a store product"""
    try:
        store = Store.objects.get(owner=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get the store product
    store_product = get_object_or_404(StoreProduct, id=product_id, store=store)
    
    if request.method == 'POST':
        try:
            # Update store product details
            store_product.price = float(request.POST.get('price', store_product.price))
            store_product.stock_quantity = int(request.POST.get('stock_quantity', store_product.stock_quantity))
            store_product.is_available = request.POST.get('is_available') == 'on'
            store_product.is_featured = request.POST.get('is_featured') == 'on'
            store_product.discount_percentage = int(request.POST.get('discount_percentage', 0)) if request.POST.get('discount_percentage') else None
            
            # Update base product details if provided
            if request.POST.get('description'):
                store_product.product.description = request.POST.get('description')
            
            # Handle main image update
            if request.FILES.get('main_image'):
                store_product.product.image = request.FILES['main_image']
            
            # Handle additional images
            if request.FILES.get('additional_images'):
                from catalog.models import ProductImage
                # Add new additional images
                for image_file in request.FILES.getlist('additional_images'):
                    if store_product.product.can_add_image():
                        ProductImage.objects.create(
                            product=store_product.product,
                            image=image_file,
                            sort_order=store_product.product.additional_images_count + 1
                        )
            
            # Handle image deletion
            if request.POST.get('delete_images'):
                from catalog.models import ProductImage
                image_ids = request.POST.get('delete_images').split(',')
                ProductImage.objects.filter(
                    id__in=image_ids, 
                    product=store_product.product
                ).delete()
            
            store_product.product.save()
            store_product.save()
            messages.success(request, f'Product "{store_product.product.name}" updated successfully!')
            
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            
        return redirect('stores:inventory_management')
    
    from catalog.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = {
        'store': store,
        'store_product': store_product,
        'categories': categories,
    }
    return render(request, 'stores/edit_product.html', context)


@store_required
def delete_store_product(request, product_id):
    """Delete a store product"""
    try:
        store = Store.objects.get(owner=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get the store product
    store_product = get_object_or_404(StoreProduct, id=product_id, store=store)
    
    if request.method == 'POST':
        product_name = store_product.product.name
        store_product.delete()
        messages.success(request, f'Product "{product_name}" removed from your inventory!')
        return redirect('stores:inventory_management')
    
    context = {
        'store': store,
        'store_product': store_product,
    }
    return render(request, 'stores/delete_product.html', context)


@store_required
def delivery_agents(request):
    """View delivery agents - Only accessible by store owners and staff"""
    try:
        store = Store.objects.get(owner=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get delivery agents in the store's coverage area
    from locations.models import ZipArea
    from stores.models import StoreZipCoverage
    
    # Get ZIP areas served by this store
    served_zip_areas = ZipArea.objects.filter(
        store_coverages__store=store,
        store_coverages__is_active=True,
        is_active=True
    ).distinct()
    
    # Get delivery agents that serve any of the ZIP areas this store serves
    from delivery_new.models import DeliveryAgent
    
    # Combine both conditions into a single QuerySet using Q to avoid union issues
    from django.db.models import Q

    agents = DeliveryAgent.objects.filter(
        Q(store=store)
    ).select_related('user').distinct().order_by('-is_available', 'user__first_name')
    
    # Separate available and unavailable agents
    available_agents = agents.filter(is_available=True)
    unavailable_agents = agents.filter(is_available=False)
    
    context = {
        'store': store,
        'agents': agents,
        'available_agents': available_agents,
        'unavailable_agents': unavailable_agents,
        'served_zip_areas': served_zip_areas,
    }
    
    return render(request, 'stores/delivery_agents.html', context)


@store_required
def new_orders_count(request):
    """AJAX endpoint to get new orders count - Only accessible by store owners and staff"""
    try:
        store = Store.objects.get(owner=request.user)
        
        pending_orders = Order.objects.filter(
            store=store,
            status='pending'
        ).count()
        
        new_orders = Order.objects.filter(
            store=store,
            status='pending',
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        return JsonResponse({
            'success': True,
            'pending_orders': pending_orders,
            'new_orders': new_orders,
        })
        
    except Store.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Store not found'
        })


@store_required
def update_order_status(request):
    """AJAX endpoint to update order status - Only accessible by store owners"""
    if request.method == 'POST':
        try:
            # Get the store for the current user
            try:
                if request.user.user_type == 'store_owner':
                    store = Store.objects.get(owner=request.user)
                else:
                    return JsonResponse({'success': False, 'message': 'Unauthorized user type'})
            except Store.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Store not found'})
            
            order_id = request.POST.get('order_id')
            order_number = request.POST.get('order_number')  # Also check for order_number
            status = request.POST.get('status')

            # Try to find order by ID or order_number
            if order_id:
                order = get_object_or_404(Order, id=order_id, store=store)
            elif order_number:
                order = get_object_or_404(Order, order_number=order_number, store=store)
            else:
                return JsonResponse({'success': False, 'message': 'Order ID or Order Number required'})

            # Validate status choice
            valid_statuses = [c[0] for c in Order._meta.get_field('status').choices]
            if status not in valid_statuses:
                return JsonResponse({
                    'success': False, 
                    'message': 'Invalid status', 
                    'posted_status': status, 
                    'valid_statuses': valid_statuses
                })

            # Use OrderStatusService for proper validation and history tracking
            from orders.services import OrderStatusService
            success, message = OrderStatusService.update_order_status(
                order=order,
                new_status=status,
                updated_by=request.user,
                notes=f'Status updated by {request.user.get_full_name()}'
            )

            if success:
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'new_status': order.status,
                    'status_display': order.get_status_display(),
                })
            else:
                return JsonResponse({'success': False, 'message': message})
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': str(e), 
                'posted_order_id': request.POST.get('order_id'), 
                'posted_status': request.POST.get('status')
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


@store_required
def toggle_store_status(request):
    """AJAX endpoint to toggle store open/closed status"""
    if request.method == 'POST':
        try:
            if request.user.user_type == 'store_owner':
                store = Store.objects.get(owner=request.user)
            else:
                store = Store.objects.get(owner=request.user)
            
            # Toggle store status
            if store.status == 'open':
                store.status = 'closed'
            else:
                store.status = 'open'
            
            store.save()
            
            return JsonResponse({
                'success': True,
                'status': store.status,
                'message': f'Store is now {store.status}'
            })
            
        except Store.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Store not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


class UpdateInventoryView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})


@store_required
def manage_zip_coverage(request):
    """View for store managers to select ZIP areas they serve"""
    try:
        store = Store.objects.get(owner=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    from .forms import StoreZipCoverageForm
    
    if request.method == 'POST':
        form = StoreZipCoverageForm(request.POST, store=store)
        if form.is_valid():
            form.save()
            messages.success(request, 'ZIP coverage areas updated successfully!')
            return redirect('stores:manage_zip_coverage')
    else:
        form = StoreZipCoverageForm(store=store)
    
    context = {
        'store': store,
        'form': form,
        'current_coverage': store.zip_coverages.filter(is_active=True).select_related('zip_area'),
    }
    
    return render(request, 'stores/manage_zip_coverage.html', context)


@login_required
def agent_zip_coverage(request):
    """View for delivery agents to select ZIP areas they can serve - MOVED TO DELIVERY APP"""
    # This function has been moved to delivery/views.py
    return redirect('delivery:agent_zip_coverage')


@store_required
def cancel_order(request, order_id):
    """Cancel an order with reason and automatic refund for prepaid orders"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify store has permission to cancel this order
    user_stores = Store.objects.filter(
        Q(owner=request.user)
    ).values_list('id', flat=True)
    
    if order.store.id not in user_stores:
        messages.error(request, 'You do not have permission to cancel this order.')
        return redirect('stores:order_detail', order_number=order.order_number)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        details = request.POST.get('details', '')
        
        try:
            # Use the order's cancel method with user parameter
            success, message = order.cancel_order(request.user, reason, details)
            
            if success:
                messages.success(request, f'Order cancelled successfully. {message}')
            else:
                messages.error(request, f'Failed to cancel order: {message}')
                
        except Exception as e:
            messages.error(request, f'Error cancelling order: {str(e)}')
    
    return redirect('stores:order_detail', order_number=order.order_number)


@store_required 
def process_refund(request, order_id):
    """Process refund for delivered order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify store has permission to refund this order
    user_stores = Store.objects.filter(
        Q(owner=request.user)
    ).values_list('id', flat=True)
    
    if order.store.id not in user_stores:
        messages.error(request, 'You do not have permission to process refund for this order.')
        return redirect('stores:order_detail', order_number=order.order_number)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        amount = request.POST.get('amount')
        details = request.POST.get('details', '')
        
        try:
            # Use the order's refund method with user parameter
            success, message = order.initiate_refund(request.user, float(amount), reason, details)
            
            if success:
                messages.success(request, f'Refund processed successfully. {message}')
            else:
                messages.error(request, f'Failed to process refund: {message}')
                
        except ValueError:
            messages.error(request, 'Invalid refund amount.')
        except Exception as e:
            messages.error(request, f'Error processing refund: {str(e)}')
    
    return redirect('stores:order_detail', order_number=order.order_number)


@store_required
def add_order_note(request, order_id):
    """Add note to order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify store has permission to add notes to this order
    user_stores = Store.objects.filter(
        Q(owner=request.user)
    ).values_list('id', flat=True)
    
    if order.store.id not in user_stores:
        messages.error(request, 'You do not have permission to add notes to this order.')
        return redirect('stores:order_detail', order_number=order.order_number)
    
    if request.method == 'POST':
        note_type = request.POST.get('note_type', 'general')
        content = request.POST.get('content', '')
        
        if content.strip():
            # For now, just add to order notes (can be enhanced with separate notes model)
            if not order.notes:
                order.notes = ""
            
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
            note_prefix = {
                'general': '📝 General',
                'preparation': '👨‍🍳 Preparation', 
                'delivery': '🚚 Delivery',
                'customer_issue': '❗ Customer Issue'
            }.get(note_type, '📝 Note')
            
            new_note = f"\n[{timestamp}] {note_prefix}: {content}"
            order.notes += new_note
            order.save()
            
            messages.success(request, f'{note_prefix} added successfully!')
        else:
            messages.error(request, 'Please provide note content.')
    
    return redirect('stores:order_detail', order_number=order.order_number)
