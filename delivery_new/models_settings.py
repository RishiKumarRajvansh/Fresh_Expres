from django.db import models
from core.models import TimeStampedModel

class DeliverySettings(TimeStampedModel):
    """Model for storing delivery-related settings"""
    
    # Basic delivery fees
    base_delivery_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=40.00,
        help_text="Base delivery fee in ₹"
    )
    
    # Distance-based fees
    fee_per_km = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00,
        help_text="Additional fee per km in ₹"
    )
    
    # Minimum and maximum fees
    minimum_delivery_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=30.00,
        help_text="Minimum delivery fee in ₹"
    )
    maximum_delivery_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=150.00,
        help_text="Maximum delivery fee in ₹"
    )
    
    # Fee calculation method
    CALCULATION_METHODS = [
        ('fixed', 'Fixed Rate'),
        ('distance', 'Distance-Based'),
        ('order_value', 'Order Value-Based')
    ]
    calculation_method = models.CharField(
        max_length=20,
        choices=CALCULATION_METHODS,
        default='fixed',
        help_text="Method to calculate delivery fees"
    )
    
    # Order value thresholds for free delivery
    free_delivery_threshold = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=500.00,
        help_text="Order value above which delivery is free in ₹"
    )
    
    # Agent payout percentage
    agent_payout_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=80.00,
        help_text="Percentage of delivery fee paid to agent"
    )
    
    class Meta:
        verbose_name = "Delivery Settings"
        verbose_name_plural = "Delivery Settings"
    
    def __str__(self):
        return f"Delivery Settings (ID: {self.id})"
    
    def calculate_delivery_fee(self, distance=None, order_value=None):
        """Calculate delivery fee based on settings and inputs"""
        if self.calculation_method == 'fixed':
            fee = self.base_delivery_fee
        
        elif self.calculation_method == 'distance' and distance:
            fee = self.base_delivery_fee + (distance * self.fee_per_km)
        
        elif self.calculation_method == 'order_value' and order_value:
            # Free delivery above threshold
            if order_value >= self.free_delivery_threshold:
                return 0.00
                
            # Otherwise, base fee with small discount for larger orders
            discount_factor = min(0.5, order_value / (self.free_delivery_threshold * 2))
            fee = self.base_delivery_fee * (1 - discount_factor)
        else:
            fee = self.base_delivery_fee
        
        # Apply min/max constraints
        fee = max(fee, self.minimum_delivery_fee)
        fee = min(fee, self.maximum_delivery_fee)
        
        # Free delivery check for any calculation method
        if order_value and order_value >= self.free_delivery_threshold:
            return 0.00
            
        return fee
    
    def calculate_agent_payout(self, delivery_fee):
        """Calculate agent payout based on delivery fee and settings"""
        return (delivery_fee * self.agent_payout_percentage / 100)
