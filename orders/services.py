"""
Order Management Services

This module provides comprehensive order management functionality including:
- Order status transitions with validation
- Automated workflow management
- Status history tracking
- Notification triggers
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Order, OrderStatusHistory
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class OrderStatusService:
    """Service for managing order status transitions"""
    
    # Define valid status transitions
    VALID_TRANSITIONS = {
        'placed': ['confirmed', 'cancelled'],
        'confirmed': ['preparing'],  # Removed 'cancelled' - only admin can cancel confirmed orders
        'preparing': ['packed'],     # Removed 'cancelled' - no cancellation after confirmation
        'packed': ['ready_for_pickup'],
        'ready_for_pickup': ['handed_to_delivery'],
        'handed_to_delivery': ['out_for_delivery'],
        'out_for_delivery': ['delivered'],
        'delivered': ['refunded'],  # Only if there's an issue
        'cancelled': [],  # Terminal state
        'refunded': [],   # Terminal state
    }
    
    # Status that require payment to be completed
    PAYMENT_REQUIRED_STATUSES = ['confirmed', 'preparing', 'packed', 'ready_for_pickup', 
                                'handed_to_delivery', 'out_for_delivery', 'delivered']
    
    @classmethod
    def update_order_status(cls, order, new_status, updated_by=None, notes=None, force=False):
        """
        Update order status with validation and history tracking
        
        Args:
            order: Order instance
            new_status: New status to transition to
            updated_by: User making the change
            notes: Optional notes for the status change
            force: Skip validation checks (use carefully)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Validate status transition
            if not force and not cls.can_transition_to(order.status, new_status):
                return False, f"Invalid status transition from {order.status} to {new_status}"
            
            # Check payment requirements
            if new_status in cls.PAYMENT_REQUIRED_STATUSES:
                if order.payment_status != 'paid' and order.payment_method != 'cod':
                    return False, f"Payment must be completed before moving to {new_status}"
            
            # Store old status for history
            old_status = order.status
            
            # Update order status
            order.status = new_status
            
            # Handle specific status transitions
            if new_status == 'handed_to_delivery':
                order.handover_to_delivery_time = timezone.now()
            elif new_status == 'delivered':
                order.actual_delivery_time = timezone.now()
            
            # Save the order
            order.save()
            
            # Handle automatic agent assignment for packed orders
            if new_status == 'packed':
                assignment = cls._auto_assign_delivery_agent(order)
                if assignment:
                    # If agent was assigned, update status to ready_for_pickup
                    order.status = 'ready_for_pickup'
                    order.save()
                    logger.info(f"Order {order.order_number} auto-transitioned to ready_for_pickup after agent assignment")
            
            # Create status history record
            if updated_by:
                OrderStatusHistory.objects.create(
                    order=order,
                    status=new_status,
                    notes=notes,
                    updated_by=updated_by
                )
            
            # Trigger notifications
            cls._trigger_status_notifications(order, old_status, new_status)
            
            logger.info(f"Order {order.order_number} status updated from {old_status} to {new_status}")
            return True, f"Order status updated to {new_status}"
            
        except Exception as e:
            logger.error(f"Failed to update order {order.order_number} status: {str(e)}")
            return False, f"Error updating status: {str(e)}"
    
    @classmethod
    def can_transition_to(cls, current_status, new_status):
        """Check if status transition is valid"""
        if current_status == new_status:
            return False  # No change needed
        return new_status in cls.VALID_TRANSITIONS.get(current_status, [])
    
    @classmethod
    def get_next_possible_statuses(cls, current_status):
        """Get list of possible next statuses with display names"""
        next_status_codes = cls.VALID_TRANSITIONS.get(current_status, [])
        
        # Import Order model to get status choices
        from .models import Order
        status_choices = dict(Order.ORDER_STATUS)
        
        # Return tuples of (status_code, display_name)
        return [(status, status_choices.get(status, status)) for status in next_status_codes]
    
    @classmethod
    def _trigger_status_notifications(cls, order, old_status, new_status):
        """Trigger notifications for status changes"""
        # Import here to avoid circular imports
        from core.services_notifications import PushNotificationService
        
        try:
            # Customer notifications
            if new_status in ['confirmed', 'preparing', 'packed', 'out_for_delivery', 'delivered']:
                # Use PushNotificationService instead of NotificationService
                # For now, we'll log the notification - can be enhanced later
                logger.info(f"Status change notification: Order {order.order_number} status changed from {old_status} to {new_status}")
                
            # Store notifications
            if new_status in ['placed', 'cancelled']:
                logger.info(f"Store notification: Order {order.order_number} status changed from {old_status} to {new_status}")
                
        except Exception as e:
            logger.warning(f"Failed to send notifications for order {order.order_number}: {str(e)}")
    
    @classmethod
    def _auto_assign_delivery_agent(cls, order):
        """Automatically assign delivery agent when order is packed"""
        try:
            # Import here to avoid circular imports
            from delivery.services import DeliveryAssignmentService
            from delivery.models import DeliveryAssignment
            
            # Check if already assigned (check database directly)
            if DeliveryAssignment.objects.filter(order=order).exists():
                logger.info(f"Order {order.order_number} already has delivery assignment")
                return None
                
            # Attempt automatic assignment
            assignment = DeliveryAssignmentService.assign_order_to_agent(order=order)
            
            if assignment:
                logger.info(f"Order {order.order_number} automatically assigned to agent {assignment.agent.user.get_full_name()}")
                return assignment
            else:
                logger.warning(f"Failed to automatically assign agent to order {order.order_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error in auto agent assignment for order {order.order_number}: {str(e)}")
            return None
    
    @classmethod
    def get_orders_by_status(cls, status, store=None, user=None):
        """Get orders filtered by status"""
        queryset = Order.objects.filter(status=status)
        
        if store:
            queryset = queryset.filter(store=store)
        if user:
            queryset = queryset.filter(user=user)
            
        return queryset.order_by('-created_at')
    
    @classmethod
    def get_pending_orders(cls, store=None):
        """Get orders that need attention (placed, confirmed, preparing)"""
        pending_statuses = ['placed', 'confirmed', 'preparing']
        return cls.get_orders_by_status_list(pending_statuses, store=store)
    
    @classmethod
    def get_orders_by_status_list(cls, status_list, store=None, user=None):
        """Get orders filtered by multiple statuses"""
        queryset = Order.objects.filter(status__in=status_list)
        
        if store:
            queryset = queryset.filter(store=store)
        if user:
            queryset = queryset.filter(user=user)
            
        return queryset.order_by('-created_at')


class OrderWorkflowService:
    """Service for automated order workflow management"""
    
    @classmethod
    def auto_confirm_paid_orders(cls):
        """Automatically confirm orders that have been paid"""
        placed_orders = Order.objects.filter(
            status='placed',
            payment_status='paid'
        )
        
        confirmed_count = 0
        for order in placed_orders:
            success, message = OrderStatusService.update_order_status(
                order=order,
                new_status='confirmed',
                notes="Auto-confirmed after payment completion"
            )
            if success:
                confirmed_count += 1
        
        return confirmed_count
    
    @classmethod
    def handle_payment_success(cls, order, payment_details=None):
        """Handle successful payment for an order"""
        try:
            # Update payment status
            order.payment_status = 'paid'
            if payment_details:
                order.payment_details = payment_details
            order.save()
            
            # Auto-confirm if order is still placed
            if order.status == 'placed':
                OrderStatusService.update_order_status(
                    order=order,
                    new_status='confirmed',
                    notes="Auto-confirmed after successful payment"
                )
            
            logger.info(f"Payment successful for order {order.order_number}")
            return True, "Payment processed successfully"
            
        except Exception as e:
            logger.error(f"Failed to handle payment success for order {order.order_number}: {str(e)}")
            return False, str(e)
    
    @classmethod
    def handle_payment_failure(cls, order, error_details=None):
        """Handle payment failure for an order"""
        try:
            order.payment_status = 'failed'
            if error_details:
                order.payment_details = error_details
            order.save()
            
            # Send notification to customer
            from core.services_notifications import NotificationService
            NotificationService.notify_payment_failed(order.user, order)
            
            logger.warning(f"Payment failed for order {order.order_number}")
            return True, "Payment failure handled"
            
        except Exception as e:
            logger.error(f"Failed to handle payment failure for order {order.order_number}: {str(e)}")
            return False, str(e)


class OrderAnalyticsService:
    """Service for order analytics and reporting"""
    
    @classmethod
    def get_order_stats(cls, store=None, date_from=None, date_to=None):
        """Get comprehensive order statistics"""
        queryset = Order.objects.all()
        
        if store:
            queryset = queryset.filter(store=store)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        stats = {
            'total_orders': queryset.count(),
            'total_revenue': sum(order.total_amount for order in queryset),
            'status_breakdown': {},
            'payment_status_breakdown': {},
            'average_order_value': 0,
        }
        
        # Calculate status breakdown
        for status_code, status_name in Order.ORDER_STATUS:
            count = queryset.filter(status=status_code).count()
            stats['status_breakdown'][status_code] = {
                'name': status_name,
                'count': count
            }
        
        # Calculate payment status breakdown
        for payment_status in ['pending', 'paid', 'failed', 'refunded']:
            count = queryset.filter(payment_status=payment_status).count()
            stats['payment_status_breakdown'][payment_status] = count
        
        # Calculate average order value
        if stats['total_orders'] > 0:
            stats['average_order_value'] = stats['total_revenue'] / stats['total_orders']
        
        return stats
