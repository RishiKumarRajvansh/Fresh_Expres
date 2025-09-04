from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, Http404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import logging
import json
from decimal import Decimal

from .models import Cart, CartItem, Order, OrderItem
from catalog.models import StoreProduct
from stores.models import Store
from locations.models import Address
from core.models import Setting

class CartView(TemplateView):
    template_name = 'orders/cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated:
            # Get all active carts and filter out empty ones
            all_carts = Cart.objects.filter(user=self.request.user, is_active=True).select_related('store')
            carts = [cart for cart in all_carts if cart.items.count() > 0]  # Only carts with items
            
            context['carts'] = carts
            
            if carts:  # Only calculate if there are non-empty carts
                # Calculate totals
                total_quantity = sum(cart.total_items for cart in carts)
                subtotal = sum(cart.subtotal for cart in carts)
                
                # Get configurable delivery fee from settings
                try:
                    delivery_fee_setting = Setting.objects.get(key='delivery_fee', is_active=True)
                    base_delivery_fee = Decimal(delivery_fee_setting.value)
                except Setting.DoesNotExist:
                    base_delivery_fee = Decimal('50.00')  # Default fallback
                
                try:
                    free_delivery_threshold_setting = Setting.objects.get(key='free_delivery_threshold', is_active=True)
                    free_delivery_threshold = Decimal(free_delivery_threshold_setting.value)
                except Setting.DoesNotExist:
                    free_delivery_threshold = Decimal('500.00')  # Default fallback
                
                # Calculate delivery fee based on threshold
                delivery_fee = Decimal('0.00') if subtotal >= free_delivery_threshold else base_delivery_fee
                
                discount = Decimal('0.00')  # You can add discount logic here
                grand_total = subtotal + delivery_fee - discount
                
                context['total_quantity'] = total_quantity
                context['subtotal'] = subtotal
                context['delivery_fee'] = delivery_fee
                context['discount'] = discount
                context['grand_total'] = grand_total
                context['free_delivery_threshold'] = free_delivery_threshold
                
                # Legacy variable names for backward compatibility
                context['total_items'] = total_quantity
                context['total_amount'] = grand_total
            else:
                # No items in any cart - show empty state
                context['total_quantity'] = 0
                context['subtotal'] = Decimal('0.00')
                context['delivery_fee'] = Decimal('0.00')
                context['discount'] = Decimal('0.00')
                context['grand_total'] = Decimal('0.00')
                context['total_items'] = 0
                context['total_amount'] = Decimal('0.00')
                context['free_delivery_threshold'] = Decimal('500.00')
        else:
            context['carts'] = []
            context['total_quantity'] = 0
            context['subtotal'] = Decimal('0.00')
            context['delivery_fee'] = Decimal('0.00')
            context['discount'] = Decimal('0.00')
            context['grand_total'] = Decimal('0.00')
            context['total_items'] = 0
            context['total_amount'] = Decimal('0.00')
            context['free_delivery_threshold'] = Decimal('500.00')
            
        return context

class StoreCartView(TemplateView):
    template_name = 'orders/store_cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_id = kwargs.get('store_id')
        store = get_object_or_404(Store, id=store_id)
        
        if self.request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=self.request.user, store=store, is_active=True)
                context['cart'] = cart
                context['cart_items'] = cart.items.all().select_related('store_product__product')
            except Cart.DoesNotExist:
                context['cart'] = None
                context['cart_items'] = []
        
        context['store'] = store
        return context

@csrf_exempt
def add_to_cart_view(request):
    """Simple function-based view for adding items to cart"""
        
    if request.method == 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Use POST method to add items to cart'
        })
    
    if request.method != 'POST':
                return JsonResponse({
            'success': False,
            'message': 'Method not allowed'
        }, status=405)
    
    # Handle both JSON and form data
    content_type = (request.content_type or '')
    
    try:
        if content_type.startswith('application/json'):
            raw_body = request.body.decode('utf-8') if request.body else ''
            data = json.loads(raw_body) if raw_body else {}
        else:
            data = request.POST
                
        store_product_id = data.get('store_product_id')
        quantity = int(data.get('quantity', 1))
                
        if not store_product_id:
            return JsonResponse({
                'success': False,
                'message': 'Product ID is required',
                'debug': {
                    'parsed_data': data,
                    'parsed_data_keys': list(data.keys()) if hasattr(data, 'keys') else []
                }
            })
        
        store_product = get_object_or_404(StoreProduct, id=store_product_id)
        
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Please login to add items to cart',
            })
        
        # Check if product is available
        if not store_product.is_available:
            return JsonResponse({
                'success': False,
                'message': 'Product is currently not available'
            })
        
        # Get or create cart for this store
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            store=store_product.store,
            defaults={'is_active': True}
        )
        
        # Ensure cart is active
        if not cart.is_active:
            cart.is_active = True
            cart.save()
        
        # Get or create cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            store_product=store_product,
            defaults={
                'quantity': quantity,
                'price_at_add': store_product.price
            }
        )
        
        if not created:
            # Update quantity if item already exists
            cart_item.quantity += quantity
            cart_item.save()

        # Remove from wishlist if added from there (per workflow requirement)
        from accounts.models import Wishlist
        try:
            wishlist_item = Wishlist.objects.filter(
                user=request.user,
                store_product=store_product
            ).first()
            if wishlist_item:
                wishlist_item.delete()
        except:
            pass  # Silent fail if wishlist removal fails

        # Get updated counts for navbar
        from core.cart_utils import update_navbar_counts
        response_data = update_navbar_counts(request, {
            'cart_total': str(cart.subtotal),
            'message': f'Added {store_product.product.name} to cart'
        })
        
        return JsonResponse({
            'success': True,
            **response_data
        })
            
    except Exception as e:
        # Include the exception message to help debug frontend failures
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

# DISABLED - Using function-based view instead
"""
@method_decorator(csrf_exempt, name='dispatch')
class AddToCartView(View):
    http_method_names = ['post', 'get']
    
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'success': False,
            'message': 'Use POST method to add items to cart'
        })
    
    def post(self, request, *args, **kwargs):
        try:
            # Handle both JSON and form data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            store_product_id = data.get('store_product_id')
            quantity = int(data.get('quantity', 1))
            
            if not store_product_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Product ID is required'
                })
            
            store_product = get_object_or_404(StoreProduct, id=store_product_id)
            
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'message': 'Please login to add items to cart'
                })
            
            # Check if product is available
            if not store_product.is_available:
                return JsonResponse({
                    'success': False,
                    'message': 'Product is currently not available'
                })
            
            # Get or create cart for this store
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                store=store_product.store,
                defaults={'is_active': True}
            )
            
            # Get or create cart item
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                store_product=store_product,
                defaults={
                    'quantity': quantity,
                    'price_at_add': store_product.price
                }
            )
            
            if not created:
                # Update quantity if item already exists
                cart_item.quantity += quantity
                cart_item.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Product added to cart successfully',
                'cart_count': cart.total_items,
                'cart_total': str(cart.subtotal)
            })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error adding to cart: {str(e)}'
            })
"""

@method_decorator(csrf_exempt, name='dispatch')
class UpdateCartView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            cart_item_id = data.get('cart_item_id')
            quantity = int(data.get('quantity', 1))
            
            if request.user.is_authenticated:
                cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
                
                if quantity <= 0:
                    cart_item.delete()
                    message = 'Item removed from cart'
                else:
                    cart_item.quantity = quantity
                    cart_item.save()
                    message = 'Cart updated'
                
                # Get updated counts for navbar
                from core.cart_utils import update_navbar_counts
                response_data = update_navbar_counts(request, {
                    'message': message,
                    'cart_total': str(cart_item.cart.subtotal) if quantity > 0 else '0.00'
                })
                
                return JsonResponse({
                    'success': True,
                    **response_data
                })
            else:
                return JsonResponse({'success': False, 'message': 'Authentication required'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

@method_decorator(csrf_exempt, name='dispatch')
class RemoveFromCartView(TemplateView):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            cart_item_id = data.get('cart_item_id')
            
            if request.user.is_authenticated:
                cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
                cart_item.delete()
                
                # Get updated counts for navbar
                from core.cart_utils import update_navbar_counts
                response_data = update_navbar_counts(request, {
                    'message': 'Item removed from cart'
                })
                
                return JsonResponse({
                    'success': True,
                    **response_data
                })
            else:
                return JsonResponse({'success': False, 'message': 'Authentication required'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

@method_decorator(csrf_exempt, name='dispatch')
class ClearCartView(TemplateView):
    def post(self, request, *args, **kwargs):
        try:
            if request.user.is_authenticated:
                store_id = request.POST.get('store_id')
                if store_id:
                    Cart.objects.filter(user=request.user, store_id=store_id).delete()
                else:
                    Cart.objects.filter(user=request.user).delete()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Cart cleared successfully'
                })
            else:
                return JsonResponse({'success': False, 'message': 'Authentication required'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get store_code from URL parameter
        store_code = kwargs.get('store_code')
        
        if store_code:
            # Get cart for specific store
            try:
                store = Store.objects.get(store_code=store_code)
                carts = Cart.objects.filter(
                    user=self.request.user, 
                    store=store,
                    is_active=True
                ).select_related('store').prefetch_related('items__store_product__product')
            except Store.DoesNotExist:
                # Redirect to cart if store not found
                from django.shortcuts import redirect
                return redirect('orders:cart')
        else:
            # Get user's active carts for all stores
            carts = Cart.objects.filter(
                user=self.request.user, 
                is_active=True
            ).select_related('store').prefetch_related('items__store_product__product')
        
        # Get user's addresses
        addresses = Address.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')
        
        total_items = sum(cart.total_items for cart in carts)
        total_amount = sum(cart.subtotal for cart in carts)
        
        context.update({
            'carts': carts,
            'addresses': addresses,
            'user_default_address': addresses.filter(is_default=True).first(),
            'total_items': total_items,
            'total_amount': total_amount,
            'store_code': store_code,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle checkout form submission"""
        try:
            # Get selected address - check both possible field names
            address_id = request.POST.get('delivery_address_id') or request.POST.get('delivery_address')
            
            # Get selected payment method
            payment_method = request.POST.get('payment_method', 'cod')
            
            if not address_id:
                from django.contrib import messages
                messages.error(request, 'Please select a delivery address.')
                return self.get(request, *args, **kwargs)
            
            # Get user's active carts
            store_code = kwargs.get('store_code')
            if store_code:
                try:
                    store = Store.objects.get(store_code=store_code)
                    carts = Cart.objects.filter(
                        user=request.user, 
                        store=store,
                        is_active=True
                    )
                except Store.DoesNotExist:
                    return redirect('orders:cart')
            else:
                carts = Cart.objects.filter(user=request.user, is_active=True)
            
            if not carts.exists():
                return redirect('orders:cart')
            
            # Create orders for each cart
            orders_created = []
            for cart in carts:
                # Calculate order totals
                subtotal = cart.subtotal
                # Prevent order creation if the store is closed
                if cart.store.status != 'open':
                    # Return the user to cart with an error message
                    from django.contrib import messages
                    messages.error(request, f"Store '{cart.store.name}' is currently closed and cannot accept orders.")
                    return redirect('orders:cart')
                delivery_fee = Decimal('0.00')  # Free delivery for now
                tax_amount = Decimal('0.00')   # No tax for now
                discount_amount = Decimal('0.00')  # No discount for now
                total_amount = subtotal + delivery_fee + tax_amount - discount_amount
                
                order = Order.objects.create(
                    user=request.user,
                    store=cart.store,
                    delivery_address_id=address_id,
                    status='placed',
                    payment_method=payment_method,  # Use selected payment method
                    subtotal=subtotal,
                    delivery_fee=delivery_fee,
                    tax_amount=tax_amount,
                    discount_amount=discount_amount,
                    total_amount=total_amount
                )
                
                # Create order items
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        store_product=cart_item.store_product,
                        quantity=cart_item.quantity,
                        unit_price=cart_item.price_at_add
                    )
                
                # Mark cart as inactive
                cart.is_active = False
                cart.save()
                
                orders_created.append(order)
            
            # Handle payment based on selected method
            if payment_method in ['upi', 'card']:
                # For online payments, redirect to payment processing
                if len(orders_created) == 1:
                    return redirect('orders:process_payment', order_number=orders_created[0].order_number)
                else:
                    # For multiple orders, process the first one (you might want to handle this differently)
                    return redirect('orders:process_payment', order_number=orders_created[0].order_number)
            else:
                # For COD, redirect directly to order confirmation
                if len(orders_created) == 1:
                    return redirect('orders:order_detail', order_number=orders_created[0].order_number)
                else:
                    return redirect('orders:order_list')
                
        except Exception as e:
            from django.contrib import messages
            messages.error(request, 'An error occurred while processing your order. Please try again.')
            return self.get(request, *args, **kwargs)


class ProcessPaymentView(LoginRequiredMixin, View):
    """Handle payment processing for orders"""
    
    def get(self, request, order_number):
        """Initiate payment for the order"""
        try:
            # Get the order
            order = get_object_or_404(Order, order_number=order_number, user=request.user)
            
            # Import payment processor
            from payments.phonepe_processor import PhonePeProcessor
            from payments.models_advanced import PaymentGateway
            
            # Get PhonePe gateway
            try:
                phonepe_gateway = PaymentGateway.objects.get(gateway_type='phonepe', is_active=True)
            except PaymentGateway.DoesNotExist:
                from django.contrib import messages
                messages.error(request, 'Payment gateway is currently unavailable. Please try again later.')
                return redirect('orders:cart')
            
            # Initialize PhonePe processor
            try:
                processor = PhonePeProcessor()
            except Exception as proc_error:
                from django.contrib import messages
                messages.error(request, 'Payment service initialization failed.')
                return redirect('orders:cart')
            
            # Create payment transaction
            try:
                payment_data = processor.create_payment(
                    amount=float(order.total_amount),
                    order_id=str(order.order_number),
                    user_id=str(request.user.id),
                    redirect_url=request.build_absolute_uri('/orders/cart/'),
                    callback_url=request.build_absolute_uri('/payments/phonepe/webhook/')
                )
                
                if payment_data['success']:
                    # Update order status to pending payment
                    order.status = 'payment_pending'
                    order.save()
                    
                    # Redirect to PhonePe payment page
                    payment_url = payment_data['payment_url']
                    return redirect(payment_url)
                else:
                    from django.contrib import messages
                    error_msg = payment_data.get('error', 'Unknown error')
                    messages.error(request, f'Unable to initiate payment: {error_msg}')
                    return redirect('orders:cart')
                    
            except Exception as payment_error:
                from django.contrib import messages
                messages.error(request, 'Payment processing error occurred.')
                return redirect('orders:cart')
                
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Payment initiation failed: {str(e)}')
            return redirect('orders:cart')


class CheckoutAddressView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout_address.html'

class CheckoutDeliveryView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout_delivery.html'

class CheckoutPaymentView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout_payment.html'

class CheckoutConfirmationView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout_confirmation.html'

class OrderListView(LoginRequiredMixin, ListView):
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        # Return orders for the current user, newest first
        return Order.objects.filter(user=self.request.user).select_related(
            'store', 'delivery_address'
        ).prefetch_related('items__store_product__product').order_by('-created_at')

class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    slug_field = 'order_number'
    slug_url_kwarg = 'order_number'
    
    def get_queryset(self):
        # Only allow users to view their own orders
        return Order.objects.filter(user=self.request.user).select_related(
            'user', 'store', 'delivery_address'
        ).prefetch_related('items__store_product__product')

class OrderTrackingView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/order_tracking.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_number = kwargs.get('order_number')
        
        try:
            order = Order.objects.select_related(
                'store', 'delivery_address'
            ).prefetch_related(
                'items__store_product__product'
            ).get(
                order_number=order_number,
                user=self.request.user
            )
            context['order'] = order
        except Order.DoesNotExist:
            raise Http404("Order not found")
        
        return context

class CancelOrderView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/cancel_order.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_number = kwargs.get('order_number')
        
        try:
            order = Order.objects.select_related(
                'store', 'delivery_address'
            ).prefetch_related(
                'items__store_product__product'
            ).get(
                order_number=order_number,
                user=self.request.user
            )
            context['order'] = order
            
            # Check if order can be cancelled - only pending and placed orders
            can_cancel = order.status in ['placed'] or (order.status == 'confirmed' and not self.request.user.is_staff)
            context['can_cancel'] = can_cancel
            
            if order.status == 'confirmed' and not self.request.user.is_staff:
                context['cancellation_message'] = "This order has been confirmed by the store and cannot be cancelled by customers. Only admin can modify confirmed orders."
            elif order.status in ['preparing', 'packed', 'out_for_delivery']:
                context['cancellation_message'] = "This order is already being processed and cannot be cancelled."
            elif order.status == 'delivered':
                context['cancellation_message'] = "This order has been delivered and cannot be cancelled."
                
        except Order.DoesNotExist:
            raise Http404("Order not found")
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_number = kwargs.get('order_number')
        
        try:
            order = Order.objects.get(
                order_number=order_number,
                user=request.user
            )
            
            # Check if user can cancel - only placed orders for regular users
            # Admin can cancel confirmed orders
            if not request.user.is_staff and order.status != 'placed':
                return redirect('orders:order_detail', order_number=order_number)
            
            if order.status in ['preparing', 'packed', 'out_for_delivery', 'delivered']:
                return redirect('orders:order_detail', order_number=order_number)
            
            # Get cancellation details from form
            reason = request.POST.get('reason')
            other_reason = request.POST.get('other_reason', '')
            comments = request.POST.get('comments', '')
            
            if not reason:
                return redirect('orders:cancel_order', order_number=order_number)
            
            # Update order status
            order.status = 'cancelled'
            
            # Store cancellation details in customer_notes
            cancellation_details = f"Cancelled by {'admin' if request.user.is_staff else 'customer'}\n"
            cancellation_details += f"Reason: {other_reason if reason == 'other' else reason}\n"
            if comments:
                cancellation_details += f"Comments: {comments}\n"
            cancellation_details += f"Cancelled at: {timezone.now()}"
            
            if order.customer_notes:
                order.customer_notes += f"\n\n{cancellation_details}"
            else:
                order.customer_notes = cancellation_details
                
            order.save()
            return redirect('orders:order_list')
            
        except Order.DoesNotExist:
            return redirect('orders:order_list')

class ReorderView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/reorder.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_number = kwargs.get('order_number')
        
        try:
            order = Order.objects.select_related(
                'store', 'delivery_address'
            ).prefetch_related(
                'items__store_product__product'
            ).get(
                order_number=order_number,
                user=self.request.user
            )
            context['order'] = order
        except Order.DoesNotExist:
            raise Http404("Order not found")
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_number = kwargs.get('order_number')
        
        try:
            original_order = Order.objects.prefetch_related(
                'items__store_product'
            ).get(
                order_number=order_number,
                user=request.user
            )
            
            # Add items back to cart
            for item in original_order.items.all():
                # Add to cart logic here
                pass
            return redirect('orders:cart')
            
        except Order.DoesNotExist:
            return redirect('orders:order_list')

class RateOrderView(LoginRequiredMixin, FormView):
    template_name = 'orders/rate_order.html'

class FileComplaintView(LoginRequiredMixin, FormView):
    template_name = 'orders/file_complaint.html'

class OrderSupportView(LoginRequiredMixin, TemplateView):
    """
    View to redirect users to chat support with order context
    """
    def get(self, request, *args, **kwargs):
        order_number = kwargs.get('order_number')
        
        try:
            order = Order.objects.select_related('store').get(
                order_number=order_number,
                user=request.user
            )
            
            # Redirect to chat with order context
            chat_url = f"/chat/?order_id={order.order_id}&order_number={order_number}&store_id={order.store.id}"
            return redirect(chat_url)
            
        except Order.DoesNotExist:
            return redirect('orders:order_list')

class PaymentSuccessView(TemplateView):
    template_name = 'orders/payment_success.html'

class PaymentFailureView(TemplateView):
    template_name = 'orders/payment_failure.html'

class PaymentCallbackView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class DeliverySlotsAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'slots': []})

class ApplyCouponAPIView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class OrderStatusAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'placed'})
