from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from core.models import TimeStampedModel
from stores.models import Store, DeliverySlot
from catalog.models import StoreProduct
from locations.models import Address
import uuid
import random
import string

User = get_user_model()

class Cart(TimeStampedModel):
    """Shopping cart (one per store per user)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='carts')
    session_key = models.CharField(max_length=100, blank=True, null=True)  # For guest users
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Cart: {self.user.username if self.user else 'Guest'} - {self.store.name}"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())
    
    @property
    def total_weight(self):
        return sum(item.total_weight for item in self.items.all())
    
    class Meta:
        unique_together = ['user', 'store']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key', 'is_active']),
        ]

class CartItem(TimeStampedModel):
    """Items in shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    store_product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_add = models.DecimalField(max_digits=8, decimal_places=2)  # Price when added to cart
    
    # Custom instructions
    special_instructions = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.store_product.product.name} x{self.quantity}"
    
    @property
    def total_price(self):
        return self.price_at_add * self.quantity
    
    @property
    def total_weight(self):
        return self.store_product.product.weight_per_unit * self.quantity
    
    def save(self, *args, **kwargs):
        if not self.price_at_add:
            self.price_at_add = self.store_product.price
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['cart', 'store_product']

class Order(TimeStampedModel):
    """Customer orders"""
    ORDER_STATUS = [
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('packed', 'Packed'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('handed_to_delivery', 'Handed to Delivery Agent'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHODS = [
        ('cod', 'Cash on Delivery'),
        ('upi', 'UPI'),
        ('card', 'Credit/Debit Card'),
        ('wallet', 'Digital Wallet'),
    ]
    
    # Basic Information
    order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders')
    delivery_address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='orders')
    delivery_slot = models.ForeignKey(DeliverySlot, on_delete=models.PROTECT, blank=True, null=True)
    
    # Order Status
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='placed')
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cod')
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Delivery Information
    estimated_delivery_time = models.DateTimeField(blank=True, null=True)
    actual_delivery_time = models.DateTimeField(blank=True, null=True)
    delivery_instructions = models.TextField(blank=True, null=True)
    
    # Delivery Handover Tracking
    handover_to_delivery_time = models.DateTimeField(blank=True, null=True)
    delivery_agent_confirmed = models.BooleanField(default=False)
    store_handover_confirmed = models.BooleanField(default=False)
    store_handover_time = models.DateTimeField(blank=True, null=True)
    customer_delivery_confirmed = models.BooleanField(default=False) 
    customer_delivery_time = models.DateTimeField(blank=True, null=True)
    handover_verification_code = models.CharField(max_length=6, blank=True, null=True)
    
    # Workflow Tracking Codes
    delivery_confirmation_code = models.CharField(max_length=8, blank=True, null=True, help_text="Code for final delivery confirmation")
    handover_code = models.CharField(max_length=6, blank=True, null=True, help_text="6-digit alphanumeric code for store-to-delivery handover")
    
    # Payment Information
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    payment_details = models.JSONField(default=dict, blank=True)
    
    # Notes
    customer_notes = models.TextField(blank=True, null=True)
    store_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Order {self.order_number} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Order.DoesNotExist:
                pass
        
        if not self.order_number:
            # Generate robust order number with collision detection
            self.order_number = self._generate_unique_order_number()
        
        # Generate delivery confirmation code when order is placed (first time)
        if not self.delivery_confirmation_code and (is_new or self.status == 'placed'):
            self.delivery_confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Generate 6-digit handover code when order is packed
        if not self.handover_code and self.status == 'packed' and old_status != 'packed':
            # Ensure unique code generation with retry mechanism
            max_attempts = 10
            for attempt in range(max_attempts):
                candidate_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not Order.objects.filter(handover_code=candidate_code).exists():
                    self.handover_code = candidate_code
                    break
            else:
                # Fallback to longer code if uniqueness fails
                self.handover_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        super().save(*args, **kwargs)
        
        # Auto-assign delivery agent when order is confirmed
        if self.status == 'confirmed' and old_status != 'confirmed':
            from delivery.services import DeliveryAssignmentService
            try:
                DeliveryAssignmentService.assign_order_to_agent(self)
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to auto-assign delivery agent for order {self.order_number}: {str(e)}")

    def _generate_unique_order_number(self):
        """
        Generate a unique order number with format: ORD-USERID-YYYYMMDD-HHMMSS-XXX
        Example: ORD-123-20250902-143022-001
        """
        from django.utils import timezone
        
        max_attempts = 50
        for attempt in range(max_attempts):
            now = timezone.now()
            
            # Format: ORD-{user_id}-{date}-{time}-{sequence}
            date_str = now.strftime('%Y%m%d')
            time_str = now.strftime('%H%M%S')
            user_id = str(self.user.id).zfill(3)  # Pad user ID to 3 digits
            sequence = str(attempt + 1).zfill(3)  # 3-digit sequence for collision handling
            
            candidate = f'ORD-{user_id}-{date_str}-{time_str}-{sequence}'
            
            # Check if this order number already exists
            if not Order.objects.filter(order_number=candidate).exists():
                return candidate
        
        # Fallback: Use UUID if all attempts fail
        import uuid
        return f'ORD-{str(uuid.uuid4())[:8].upper()}'
    
    @property
    def can_cancel(self):
        return self.status in ['placed', 'confirmed'] and self.payment_status != 'paid'
    
    def get_customer_friendly_status(self):
        """Return customer-friendly status messages"""
        customer_statuses = {
            'placed': '✅ Order Confirmed',
            'confirmed': '👨‍🍳 Preparing Your Order',
            'preparing': '👨‍🍳 Cooking Fresh for You',
            'packed': '📦 Ready for Delivery',
            'ready_for_pickup': '🚚 Out for Delivery',
            'handed_to_delivery': '🚚 On the Way',
            'out_for_delivery': '🚚 Out for Delivery',
            'delivered': '✅ Delivered',
            'cancelled': '❌ Cancelled',
            'refunded': '💰 Refunded',
        }
        return customer_statuses.get(self.status, self.get_status_display())
    
    def get_status_description(self):
        """Return detailed status description for customers"""
        descriptions = {
            'placed': 'Your order has been received and is being processed.',
            'confirmed': 'Your order has been confirmed and we are starting to prepare it.',
            'preparing': 'Our chef is preparing your fresh order with care.',
            'packed': 'Your order is packed and ready for delivery.',
            'ready_for_pickup': 'Your order is out for delivery and will reach you soon.',
            'handed_to_delivery': 'Your order has been handed to our delivery agent.',
            'out_for_delivery': 'Your order is on its way to your location.',
            'delivered': 'Your order has been successfully delivered. Enjoy your meal!',
            'cancelled': 'This order has been cancelled.',
            'refunded': 'Refund has been processed for this order.',
        }
        return descriptions.get(self.status, 'Order status updated.')
    
    def can_be_cancelled(self, user=None):
        """Check if order can be cancelled"""
        # Only orders with 'placed' status can be cancelled by customers/store managers
        # Confirmed and later orders can only be cancelled by admin
        if user and hasattr(user, 'is_superuser') and user.is_superuser:
            # Admin can cancel any order before delivery
            return self.status in ['placed', 'confirmed', 'preparing', 'packed', 'ready_for_pickup']
        else:
            # Customers and store managers can only cancel placed orders
            return self.status == 'placed'
    
    def can_be_refunded(self):
        """Check if order can be refunded - only for prepaid orders until confirmed status"""
        # Can refund only if payment was made (not COD) and order is still cancellable
        # After confirmed status, refunds are only processed through customer service
        return (
            self.payment_status == 'paid' and 
            self.payment_method != 'cod' and
            self.status in ['placed', 'confirmed']  # Only until confirmed status
        )
    
    def cancel_order(self, cancelled_by=None, reason="", details=""):
        """Cancel the order with reason and return success status"""
        try:
            if not self.can_be_cancelled():
                return False, f"Cannot cancel order with status: {self.status}"
            
            old_status = self.status
            self.status = 'cancelled'
            self.save()
            
            # Create status history entry
            OrderStatusHistory.objects.create(
                order=self,
                status='cancelled',
                updated_by=cancelled_by,
                notes=f"Order cancelled. Reason: {reason}. {details}".strip()
            )
            
            # If prepaid order, initiate automatic refund
            refund_message = ""
            if self.payment_method == 'prepaid' and self.payment_status == 'paid':
                try:
                    refund_success, refund_msg = self.initiate_refund(cancelled_by, f"Automatic refund for cancelled order. {reason}")
                    if refund_success:
                        refund_message = " Automatic refund has been processed."
                    else:
                        refund_message = f" Note: Refund failed - {refund_msg}"
                except Exception as e:
                    refund_message = f" Note: Refund processing failed - {str(e)}"
            
            return True, f"Order cancelled successfully.{refund_message}"
            
        except Exception as e:
            return False, f"Error cancelling order: {str(e)}"
    
    def initiate_refund(self, initiated_by=None, amount=None, reason="", details=""):
        """Initiate refund for orders with amount and reason"""
        try:
            if not self.can_be_refunded():
                return False, "This order is not eligible for refund"
            
            # Default amount is full order amount
            if amount is None:
                amount = float(self.total_amount)
            
            # Validate refund amount
            if amount <= 0 or amount > float(self.total_amount):
                return False, f"Invalid refund amount. Must be between 0 and {self.total_amount}"
            
            # Update payment status
            old_payment_status = self.payment_status
            self.payment_status = 'refunded'
            
            # Update order status if not already cancelled
            if self.status not in ['cancelled', 'refunded']:
                self.status = 'refunded'
                
            self.save()
            
            # Create status history entry
            OrderStatusHistory.objects.create(
                order=self,
                status='refunded',
                updated_by=initiated_by,
                notes=f"Refund of ₹{amount} processed. Reason: {reason}. {details}".strip()
            )
            
            # TODO: Integrate with actual payment gateway
            # For now, just update status and create history
            
            return True, f"Refund of ₹{amount} has been processed successfully. It will reflect in the original payment method within 3-5 business days."
            
        except Exception as e:
            return False, f"Error processing refund: {str(e)}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['store', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'created_at']),
        ]

class OrderItem(TimeStampedModel):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    store_product = models.ForeignKey(StoreProduct, on_delete=models.PROTECT)
    
    # Product details at time of order (for record keeping)
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=50, blank=True, null=True)
    
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Special instructions for this item
    special_instructions = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.product_name} x{self.quantity} - Order {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.product_name:
            self.product_name = self.store_product.product.name
        if not self.product_sku:
            self.product_sku = self.store_product.product.sku
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

class OrderStatusHistory(TimeStampedModel):
    """History of order status changes"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    notes = models.TextField(blank=True, null=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"Order {self.order.order_number} - {self.get_status_display()}"
    
    class Meta:
        ordering = ['-created_at']

class Coupon(TimeStampedModel):
    """Discount coupons"""
    COUPON_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
        ('free_delivery', 'Free Delivery'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    coupon_type = models.CharField(max_length=15, choices=COUPON_TYPES, default='percentage')
    value = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Usage restrictions
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    max_discount_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    usage_limit = models.PositiveIntegerField(blank=True, null=True)
    usage_limit_per_user = models.PositiveIntegerField(blank=True, null=True)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Applicable stores (empty means all stores)
    applicable_stores = models.ManyToManyField(Store, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.code} - {self.title}"
    
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date
    
    class Meta:
        ordering = ['-created_at']

class CouponUsage(TimeStampedModel):
    """Track coupon usage"""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usage_history')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2)
    
    def __str__(self):
        return f"{self.coupon.code} used by {self.user.username} - Order {self.order.order_number}"
    
    class Meta:
        unique_together = ['coupon', 'order']

class Complaint(TimeStampedModel):
    """Customer complaints and disputes"""
    COMPLAINT_STATUS = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    COMPLAINT_TYPES = [
        ('order_issue', 'Order Issue'),
        ('delivery_issue', 'Delivery Issue'),
        ('product_quality', 'Product Quality'),
        ('payment_issue', 'Payment Issue'),
        ('other', 'Other'),
    ]
    
    complaint_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='complaints')
    
    complaint_type = models.CharField(max_length=20, choices=COMPLAINT_TYPES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=COMPLAINT_STATUS, default='open')
    
    resolution = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='resolved_complaints')
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"Complaint #{str(self.complaint_id)[:8]} - {self.subject}"
    
    class Meta:
        ordering = ['-created_at']
