"""
Order and Delivery Integration
Handles the connection between order placement and delivery assignment
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from orders.models import Order
from .models import DeliveryAssignment
from .services import DeliveryAssignmentService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Order)
def auto_assign_delivery(sender, instance, created, **kwargs):
    """
    Automatically assign delivery agent when order is confirmed
    """
    if not created and instance.status == 'confirmed':
        # Check if delivery assignment already exists
        try:
            existing_assignment = DeliveryAssignment.objects.get(order=instance)
            logger.info(f"Delivery assignment already exists for order {instance.order_number}")
            return
        except DeliveryAssignment.DoesNotExist:
            pass
        
        # Create delivery assignment
        assignment = DeliveryAssignmentService.assign_order_to_agent(instance)
        
        if assignment:
            logger.info(f"Successfully assigned order {instance.order_number} to agent {assignment.agent.user.get_full_name()}")
        else:
            logger.warning(f"Failed to assign delivery agent for order {instance.order_number}")
            # TODO: Notify administrators about unassigned orders
            # send_admin_notification(instance)

def integrate_with_checkout(order):
    """
    Integration function to be called after successful checkout
    """
    try:
        # Update order status to confirmed
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()
        
        # The signal handler will automatically assign delivery
        logger.info(f"Order {order.order_number} confirmed and queued for delivery assignment")
        
        return True
    except Exception as e:
        logger.error(f"Failed to integrate order {order.order_number} with delivery system: {str(e)}")
        return False

def update_order_status_from_delivery(assignment):
    """
    Update order status based on delivery assignment status
    """
    status_mapping = {
        'assigned': 'assigned_to_delivery',
        'accepted': 'in_delivery',
        'picked_up': 'out_for_delivery',
        'delivered': 'delivered',
        'cancelled': 'delivery_cancelled'
    }
    
    new_order_status = status_mapping.get(assignment.status)
    
    if new_order_status and assignment.order.status != new_order_status:
        assignment.order.status = new_order_status
        
        # Set completion time for delivered orders
        if new_order_status == 'delivered':
            assignment.order.delivered_at = timezone.now()
        
        assignment.order.save()
        logger.info(f"Updated order {assignment.order.order_number} status to {new_order_status}")

def handle_delivery_completion(assignment):
    """
    Handle order completion workflow after delivery
    """
    try:
        # Update order status
        update_order_status_from_delivery(assignment)
        
        # TODO: Send completion email to customer
        # send_delivery_completion_email(assignment.order.user, assignment)
        
        # TODO: Update customer loyalty points
        # update_loyalty_points(assignment.order.user, assignment.order.total_amount)
        
        # TODO: Send feedback request
        # send_feedback_request(assignment.order.user, assignment.order)
        
        logger.info(f"Completed delivery workflow for order {assignment.order.order_number}")
        
    except Exception as e:
        logger.error(f"Error in delivery completion workflow: {str(e)}")

def calculate_total_with_delivery(order_items, delivery_address=None):
    """
    Calculate total order amount including delivery fee
    """
    # Calculate items total
    items_total = sum(item.price * item.quantity for item in order_items)
    
    # Calculate delivery fee (simplified - can be enhanced with actual distance)
    base_delivery_fee = 50.00  # Base delivery fee
    
    # TODO: Calculate actual delivery fee based on:
    # - Distance to delivery address
    # - Peak time multiplier
    # - Store-specific delivery charges
    
    delivery_fee = base_delivery_fee
    
    # Apply free delivery for orders above certain amount
    if items_total >= 500:  # Free delivery for orders ≥ ₹500
        delivery_fee = 0
    
    total_amount = items_total + delivery_fee
    
    return {
        'items_total': items_total,
        'delivery_fee': delivery_fee,
        'total_amount': total_amount
    }

def get_estimated_delivery_time(store, delivery_address):
    """
    Estimate delivery time based on store location and delivery address
    """
    # TODO: Integrate with Google Maps API for accurate estimates
    # For now, return default estimates based on time of day
    
    current_hour = timezone.now().hour
    
    if 11 <= current_hour <= 14:  # Lunch time
        base_time = 45
    elif 18 <= current_hour <= 21:  # Dinner time
        base_time = 50
    else:
        base_time = 35
    
    # Add random variation (±10 minutes)
    import random
    variation = random.randint(-10, 10)
    estimated_time = max(20, base_time + variation)
    
    return estimated_time

def check_delivery_availability(store, delivery_address):
    """
    Check if delivery is available for the given address from the store
    """
    # TODO: Implement actual delivery zone checking
    # For now, assume delivery is available (production should have proper validation)
    
    return {
        'available': True,
        'message': 'Delivery available',
        'estimated_time': get_estimated_delivery_time(store, delivery_address)
    }

def get_available_delivery_slots(store, delivery_date):
    """
    Get available delivery time slots for a specific date
    """
    # TODO: Implement actual slot management based on agent availability
    # For now, return default slots
    
    slots = [
        {'time': '10:00-12:00', 'available': True, 'fee': 50},
        {'time': '12:00-14:00', 'available': True, 'fee': 50},
        {'time': '14:00-16:00', 'available': True, 'fee': 50},
        {'time': '16:00-18:00', 'available': True, 'fee': 50},
        {'time': '18:00-20:00', 'available': True, 'fee': 60},  # Peak time
        {'time': '20:00-22:00', 'available': True, 'fee': 60},  # Peak time
    ]
    
    return slots

class OrderDeliveryIntegration:
    """
    Main integration class for order and delivery system
    """
    
    @staticmethod
    def process_order_for_delivery(order_data, user):
        """
        Process a new order and set up delivery
        """
        try:
            # Create the order
            order = Order.objects.create(
                user=user,
                store_id=order_data['store_id'],
                delivery_address=order_data['delivery_address'],
                phone_number=order_data['phone_number'],
                delivery_notes=order_data.get('delivery_notes', ''),
                total_amount=order_data['total_amount'],
                status='pending'
            )
            
            # Add order items
            for item_data in order_data['items']:
                # TODO: Create OrderItem objects
                pass
            
            # Integrate with delivery system
            integrate_with_checkout(order)
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to process order for delivery: {str(e)}")
            raise
    
    @staticmethod
    def get_order_tracking_url(order):
        """
        Get the tracking URL for an order
        """
        try:
            assignment = DeliveryAssignment.objects.get(order=order)
            from django.urls import reverse
            return reverse('delivery:track_order', kwargs={'assignment_id': assignment.id})
        except DeliveryAssignment.DoesNotExist:
            return None
    
    @staticmethod
    def cancel_order_delivery(order, reason="Customer requested"):
        """
        Cancel delivery for an order
        """
        try:
            assignment = DeliveryAssignment.objects.get(order=order)
            
            if assignment.status in ['delivered']:
                return False, "Cannot cancel delivered order"
            
            if assignment.status in ['picked_up']:
                return False, "Cannot cancel order that has been picked up"
            
            assignment.status = 'cancelled'
            assignment.cancellation_reason = reason
            assignment.save()
            
            # Update order status
            order.status = 'cancelled'
            order.save()
            
            # TODO: Notify agent and customer
            
            return True, "Order delivery cancelled successfully"
            
        except DeliveryAssignment.DoesNotExist:
            order.status = 'cancelled'
            order.save()
            return True, "Order cancelled successfully"
        except Exception as e:
            logger.error(f"Failed to cancel order delivery: {str(e)}")
            return False, str(e)
