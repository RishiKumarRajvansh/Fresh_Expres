"""
Delivery Assignment and Management System
Handles automatic order assignment and delivery workflow
"""

from django.db import transaction, models
from django.utils import timezone
from django.db.models import Q, Count, F, Avg
from decimal import Decimal
import logging
from .models import DeliveryAgent, DeliveryAssignment
from orders.models import Order

logger = logging.getLogger(__name__)

class DeliveryAssignmentService:
    """Service to handle automatic delivery assignments"""
    
    @staticmethod
    def assign_order_to_agent(order, manual_agent_id=None):
        """
        Assign an order to a delivery agent (auto or manual)
        """
        try:
            with transaction.atomic():
                # Check if order already has assignment
                if hasattr(order, 'delivery_assignment'):
                    return order.delivery_assignment
                
                # Manual assignment by store manager
                if manual_agent_id:
                    try:
                        selected_agent = DeliveryAgent.objects.get(
                            id=manual_agent_id,
                            store=order.store,
                            status='active'
                        )
                    except DeliveryAgent.DoesNotExist:
                        logger.error(f"Invalid agent ID {manual_agent_id} for order {order.order_number}")
                        return None
                else:
                    # Automatic assignment - find best available agent
                    selected_agent = DeliveryAssignmentService._find_best_available_agent(order)
                
                if not selected_agent:
                    logger.warning(f"No available agents for order {order.order_number}")
                    return None
                
                # Create assignment
                assignment = DeliveryAssignment.objects.create(
                    order=order,
                    agent=selected_agent,
                    status='assigned',
                    estimated_distance_km=DeliveryAssignmentService._calculate_distance(order, selected_agent),
                    estimated_time_minutes=DeliveryAssignmentService._calculate_estimated_time(order)
                )
                
                # Note: Don't update order status here to avoid circular calls
                # The status will be updated by the calling service
                
                logger.info(f"Order {order.order_number} assigned to agent {selected_agent.user.get_full_name()}")
                return assignment
                
        except Exception as e:
            logger.error(f"Failed to assign order {order.order_number}: {str(e)}")
            return None
    
    @staticmethod
    def _find_best_available_agent(order):
        """Find the best available delivery agent for an order"""
        # Find available agents for the store
        available_agents = DeliveryAgent.objects.filter(
            store=order.store,
            is_available=True,
            status='active'
        ).annotate(
            current_orders=Count(
                'assigned_orders',
                filter=Q(assigned_orders__status__in=['assigned', 'accepted', 'picked_up', 'in_transit'])
            )
        ).filter(
            current_orders__lt=F('max_concurrent_orders')
        ).order_by('current_orders', '?')  # Random selection among least busy
        
        if not available_agents.exists():
            return None
            
        # TODO: Add proximity-based selection using delivery address
        # For now, return the least busy agent
        return available_agents.first()
    
    @staticmethod
    def _calculate_distance(order, agent):
        """Calculate estimated distance between store and delivery address"""
        # TODO: Implement real distance calculation using maps API
        return Decimal('5.0')  # Default 5km
    
    @staticmethod  
    def _calculate_estimated_time(order):
        """Calculate estimated delivery time"""
        # TODO: Consider traffic, distance, and order complexity
        return 30  # Default 30 minutes
    
    @staticmethod
    def handover_to_agent(order, handover_code):
        """Handle store-to-agent handover with OTP verification"""
        try:
            assignment = order.delivery_assignment
            
            # Verify handover code
            if order.handover_code != handover_code:
                return False, "Invalid handover code"
            
            # Update assignment status
            assignment.status = 'picked_up'
            assignment.picked_up_at = timezone.now()
            assignment.save()
            
            # Update order status
            from orders.services import OrderStatusService
            OrderStatusService.update_order_status(
                order=order,
                new_status='handed_to_delivery',
                updated_by=assignment.agent.user,
                notes="Order handed over to delivery agent"
            )
            
            return True, "Order successfully handed over to delivery agent"
            
        except Exception as e:
            logger.error(f"Error in handover for order {order.order_number}: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def confirm_delivery(order, delivery_code):
        """Handle final delivery confirmation with customer OTP"""
        try:
            assignment = order.delivery_assignment
            
            # Verify delivery confirmation code
            if order.delivery_confirmation_code != delivery_code:
                return False, "Invalid delivery code"
            
            # Update assignment status
            assignment.status = 'delivered'
            assignment.delivered_at = timezone.now()
            assignment.save()
            
            # Update order status
            from orders.services import OrderStatusService
            OrderStatusService.update_order_status(
                order=order,
                new_status='delivered',
                updated_by=assignment.agent.user,
                notes="Order delivered to customer"
            )
            
            return True, "Order successfully delivered"
            
        except Exception as e:
            logger.error(f"Error in delivery confirmation for order {order.order_number}: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def reassign_order(assignment, reason=""):
        """Reassign an order to a different agent"""
        try:
            with transaction.atomic():
                old_agent = assignment.agent
                
                # Mark current assignment as cancelled
                assignment.status = 'cancelled'
                assignment.cancellation_reason = reason
                assignment.save()
                
                # Create new assignment
                new_assignment = DeliveryAssignmentService.assign_order_to_agent(assignment.order)
                
                if new_assignment:
                    logger.info(f"Order {assignment.order.order_number} reassigned from {old_agent.user.get_full_name()} to {new_assignment.agent.user.get_full_name()}")
                    return new_assignment
                else:
                    logger.error(f"Failed to reassign order {assignment.order.order_number}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error reassigning order: {str(e)}")
            return None
    
    @staticmethod
    def auto_assign_pending_orders():
        """
        Background task to assign pending orders to available agents
        This can be run as a periodic task
        """
        pending_orders = Order.objects.filter(
            status='confirmed',  # Orders ready for delivery assignment
        ).select_related('store')
        
        assignments_created = 0
        for order in pending_orders:
            assignment = DeliveryAssignmentService.assign_order_to_agent(order)
            if assignment:
                assignments_created += 1
        
        logger.info(f"Auto-assigned {assignments_created} orders to delivery agents")
        return assignments_created
    
    @staticmethod
    def handle_order_timeout(assignment):
        """Handle orders that haven't been accepted by agents"""
        if assignment.status == 'assigned':
            time_since_assignment = timezone.now() - assignment.assigned_at
            
            # If more than 10 minutes, reassign
            if time_since_assignment.total_seconds() > 600:  # 10 minutes
                DeliveryAssignmentService.reassign_order(
                    assignment, 
                    "Agent did not accept within time limit"
                )
    
    @staticmethod
    def calculate_delivery_fee(order, agent):
        """Calculate delivery fee based on distance and other factors"""
        base_fee = Decimal('50.00')  # Base delivery fee
        distance_fee = Decimal('5.00')  # Per km
        
        # TODO: Implement actual distance calculation using maps API
        estimated_distance = Decimal('5.0')  # Placeholder
        
        total_fee = base_fee + (estimated_distance * distance_fee)
        
        # Peak time multiplier
        current_hour = timezone.now().hour
        if 18 <= current_hour <= 21:  # Peak dinner time
            total_fee *= Decimal('1.2')
        
        return total_fee, estimated_distance

class DeliveryTrackingService:
    """Service for managing delivery tracking and notifications"""
    
    @staticmethod
    def update_customer_tracking(assignment):
        """Update customer with delivery tracking information"""
        # TODO: Implement customer notifications
        # - SMS updates
        # - Email updates
        # - Push notifications
        pass
    
    @staticmethod
    def estimate_delivery_time(assignment):
        """Estimate delivery time based on current location and traffic"""
        # TODO: Integrate with Google Maps API for real-time estimates
        if assignment.status == 'picked_up':
            return 25  # Default 25 minutes
        elif assignment.status == 'accepted':
            return 35  # 10 minutes to reach store + 25 minutes delivery
        else:
            return assignment.estimated_time_minutes
    
    @staticmethod
    def send_delivery_notifications(assignment, event_type):
        """Send notifications for delivery events"""
        customer = assignment.order.user
        
        notification_messages = {
            'assigned': f"Your order #{assignment.order.order_number} has been assigned to {assignment.agent.user.get_full_name()}",
            'accepted': f"Your order #{assignment.order.order_number} has been accepted and will be picked up soon",
            'picked_up': f"Your order #{assignment.order.order_number} is on the way! Estimated delivery: {DeliveryTrackingService.estimate_delivery_time(assignment)} minutes",
            'delivered': f"Your order #{assignment.order.order_number} has been delivered successfully"
        }
        
        message = notification_messages.get(event_type, '')
        
        if message:
            # TODO: Implement actual notification sending
            # - SMS via Twilio
            # - Email via Django's email backend
            # - Push notifications
            logger.info(f"Notification sent to {customer.email}: {message}")

class DeliveryAnalyticsService:
    """Service for delivery analytics and insights"""
    
    @staticmethod
    def get_agent_performance(agent, period_days=30):
        """Get performance metrics for an agent"""
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=period_days)
        
        assignments = DeliveryAssignment.objects.filter(
            agent=agent,
            assigned_at__range=[start_date, end_date]
        )
        
        total_assignments = assignments.count()
        completed = assignments.filter(status='delivered').count()
        cancelled = assignments.filter(status='cancelled').count()
        
        # Calculate average delivery time
        completed_assignments = assignments.filter(
            status='delivered',
            actual_time_minutes__isnull=False
        )
        
        avg_delivery_time = 0
        if completed_assignments.exists():
            total_time = sum(a.actual_time_minutes for a in completed_assignments)
            avg_delivery_time = total_time / completed_assignments.count()
        
        return {
            'total_assignments': total_assignments,
            'completed': completed,
            'cancelled': cancelled,
            'completion_rate': (completed / total_assignments * 100) if total_assignments > 0 else 0,
            'avg_delivery_time': avg_delivery_time,
            'total_earnings': DeliveryAssignmentService.calculate_earnings(completed_assignments)
        }
    
    @staticmethod
    def get_store_delivery_stats(store, period_days=30):
        """Get delivery statistics for a store"""
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=period_days)
        
        orders = Order.objects.filter(
            store=store,
            created_at__range=[start_date, end_date]
        )
        
        assignments = DeliveryAssignment.objects.filter(
            order__store=store,
            assigned_at__range=[start_date, end_date]
        )
        
        return {
            'total_orders': orders.count(),
            'assigned_orders': assignments.count(),
            'delivered_orders': assignments.filter(status='delivered').count(),
            'avg_delivery_time': assignments.filter(
                status='delivered',
                actual_time_minutes__isnull=False
            ).aggregate(avg=Avg('actual_time_minutes'))['avg'] or 0
        }
