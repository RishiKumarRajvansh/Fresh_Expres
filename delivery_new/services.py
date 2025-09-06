"""
Delivery services for the delivery_new app.
This module provides service classes for managing deliveries.
"""
from django.utils import timezone
from .models import DeliveryAgent, Delivery

class DeliveryService:
    """Service for managing deliveries"""
    
    @staticmethod
    def assign_order_to_agent(order):
        """Assign an order to the best available delivery agent"""
        # Find an available agent that covers the delivery area
        available_agents = DeliveryAgent.objects.filter(
            is_available=True,
            status='active',
        ).order_by('?')  # Random selection among available agents
        
        if available_agents.exists():
            agent = available_agents.first()
            
            # Create a new delivery
            delivery = Delivery.objects.create(
                order=order,
                agent=agent,
                status='assigned',
                assigned_at=timezone.now()
            )
            
            return delivery
        
        return None

# Compatibility with old service name
DeliveryAssignmentService = DeliveryService
