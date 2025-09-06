from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from core.models import TimeStampedModel
from orders.models import Order
from stores.models import Store
from locations.models import ZipArea
from .models_settings import DeliverySettings
import uuid
import random
import string

User = get_user_model()

class DeliveryAgent(TimeStampedModel):
    """Delivery Agent Model - Improved Version"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('offline', 'Offline'),
        ('on_break', 'On Break'),
        ('busy', 'Busy'),
    ]
    
    VEHICLE_CHOICES = [
        ('bicycle', 'Bicycle'),
        ('scooter', 'Scooter'),
        ('motorcycle', 'Motorcycle'),
        ('car', 'Car'),
        ('van', 'Van'),
    ]
    
    # Core fields
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_new_agent_profile')
    agent_id = models.CharField(max_length=20, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_new_agents')
    
    # Contact information
    phone_number = models.CharField(max_length=15)
    alternative_phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Status and availability
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='offline')
    is_available = models.BooleanField(default=False)
    max_concurrent_orders = models.PositiveIntegerField(default=3)
    service_area_radius = models.PositiveIntegerField(default=10, help_text="Service radius in km")
    
    # Vehicle information
    vehicle_type = models.CharField(max_length=15, choices=VEHICLE_CHOICES, default='scooter')
    vehicle_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Location tracking
    current_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    last_location_update = models.DateTimeField(blank=True, null=True)
    
    # Performance metrics
    total_deliveries = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    class Meta:
        verbose_name = "Delivery Agent"
        verbose_name_plural = "Delivery Agents"
    
    def __str__(self):
        return f"{self.agent_id} - {self.user.get_full_name() or self.user.email}"
    
    def save(self, *args, **kwargs):
        # Generate agent ID if not set
        if not self.agent_id:
            self.agent_id = self.generate_agent_id()
        super().save(*args, **kwargs)
    
    def generate_agent_id(self):
        """Generate a unique agent ID"""
        prefix = "AGT"
        random_digits = ''.join(random.choices(string.digits, k=4))
        return f"{prefix}{random_digits}"
    
    @property
    def success_rate(self):
        """Calculate the agent's delivery success rate"""
        if self.total_deliveries == 0:
            return 0
        return round((self.successful_deliveries / self.total_deliveries) * 100, 2)
    
    @property
    def current_orders_count(self):
        """Count active orders assigned to this agent"""
        return self.deliveries.filter(
            status__in=['assigned', 'accepted', 'picked_up', 'in_transit']
        ).count()
    
    @property
    def can_accept_orders(self):
        """Check if agent can accept more orders"""
        return (
            self.is_available and
            self.status == 'active' and
            self.current_orders_count < self.max_concurrent_orders
        )
    
    def get_absolute_url(self):
        """Get URL for agent's detail view"""
        return reverse('delivery_new:agent_detail', args=[self.pk])
    
    def toggle_availability(self):
        """Toggle the agent's availability status"""
        # Check if the agent has ZIP coverage
        if self.zip_coverages.filter(is_active=True).exists():
            self.is_available = not self.is_available
            if self.is_available and self.status == 'offline':
                self.status = 'active'
            elif not self.is_available and self.status == 'active':
                self.status = 'offline'
            self.save()
            return self.is_available
        else:
            # If no ZIP coverage, raise an exception
            raise ValueError("ZIP code required")


class Delivery(TimeStampedModel):
    """Improved Delivery Model - replaces DeliveryAssignment"""
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),      # Initial state when order is assigned to agent
        ('accepted', 'Accepted'),      # Agent has accepted the delivery
        ('at_store', 'At Store'),      # Agent has arrived at the store
        ('picked_up', 'Picked Up'),    # Order has been picked up from store
        ('in_transit', 'In Transit'),  # Order is being delivered
        ('delivered', 'Delivered'),    # Order has been delivered
        ('cancelled', 'Cancelled'),    # Delivery was cancelled
        ('failed', 'Failed'),          # Delivery attempt failed
    ]
    
    # Core relationships
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliveries')
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='deliveries')
    
    # Tracking information
    delivery_id = models.CharField(max_length=30, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='assigned')
    
    # Financial information
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    agent_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Timing information
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    arrived_at_store_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # OTP verification codes
    store_pickup_otp = models.CharField(max_length=6, blank=True, null=True)
    customer_delivery_otp = models.CharField(max_length=6, blank=True, null=True)
    
    # OTP verification status
    store_pickup_verified = models.BooleanField(default=False)
    customer_delivery_verified = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"Delivery {self.delivery_id} - {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        # Generate delivery ID if not set
        if not self.delivery_id:
            self.delivery_id = self.generate_delivery_id()
            
        # Generate OTPs if not set
        if not self.store_pickup_otp:
            self.store_pickup_otp = self.generate_otp()
        if not self.customer_delivery_otp:
            self.customer_delivery_otp = self.generate_otp()
        
        # Calculate delivery fee and agent payout if not already set
        if self.delivery_fee == 0:
            try:
                settings = DeliverySettings.objects.first()
                if not settings:
                    settings = DeliverySettings.objects.create()
                
                # Get delivery distance (if available)
                distance = None
                if hasattr(self.order, 'delivery_address') and hasattr(self.order.store, 'address'):
                    # This is a placeholder - in a real app, you'd calculate actual distance
                    # For now, use a random distance between 1-10 km
                    import random
                    distance = random.uniform(1, 10)
                
                # Get order value
                order_value = self.order.total_amount if hasattr(self.order, 'total_amount') else None
                
                # Calculate fee and payout
                self.delivery_fee = settings.calculate_delivery_fee(distance=distance, order_value=order_value)
                self.agent_payout = settings.calculate_agent_payout(self.delivery_fee)
                
            except Exception as e:
                # Fallback to default values if calculation fails
                self.delivery_fee = 40.00
                self.agent_payout = 32.00
            
        super().save(*args, **kwargs)
    
    def generate_delivery_id(self):
        """Generate a unique delivery ID"""
        prefix = "DEL"
        timestamp = timezone.now().strftime('%y%m%d%H%M')
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{timestamp}-{random_chars}"
    
    def generate_otp(self):
        """Generate a 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=6))
    
    def accept_delivery(self):
        """Mark delivery as accepted by agent"""
        if self.status == 'assigned':
            self.status = 'accepted'
            self.accepted_at = timezone.now()
            self.save()
            return True
        return False
    
    def arrive_at_store(self):
        """Mark agent as arrived at store"""
        if self.status == 'accepted':
            self.status = 'at_store'
            self.arrived_at_store_at = timezone.now()
            self.save()
            return True
        return False
    
    def pickup_from_store(self, otp):
        """Verify store pickup with OTP"""
        if self.status == 'at_store' and otp == self.store_pickup_otp:
            self.status = 'picked_up'
            self.picked_up_at = timezone.now()
            self.store_pickup_verified = True
            self.save()
            return True
        return False
    
    def mark_in_transit(self):
        """Mark delivery as in transit"""
        if self.status == 'picked_up':
            self.status = 'in_transit'
            self.save()
            return True
        return False
    
    def complete_delivery(self, otp):
        """Verify delivery completion with OTP"""
        if self.status in ['picked_up', 'in_transit'] and otp == self.customer_delivery_otp:
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.customer_delivery_verified = True
            
            # Update agent statistics
            self.agent.total_deliveries += 1
            self.agent.successful_deliveries += 1
            self.agent.save()
            
            self.save()
            return True
        return False
    
    def cancel_delivery(self):
        """Cancel the delivery"""
        if self.status not in ['delivered', 'cancelled', 'failed']:
            self.status = 'cancelled'
            self.save()
            return True
        return False
    
    @property
    def is_completed(self):
        """Check if delivery is completed"""
        return self.status == 'delivered'
    
    @property
    def is_active(self):
        """Check if delivery is active"""
        return self.status in ['accepted', 'at_store', 'picked_up', 'in_transit']
    
    @property
    def is_pending(self):
        """Check if delivery is pending agent action"""
        return self.status == 'assigned'
    
    def get_absolute_url(self):
        """Get URL for delivery detail view"""
        return reverse('delivery_new:delivery_detail', args=[self.pk])
        
    def get_status_color(self):
        """Get Bootstrap color class for status"""
        status_colors = {
            'assigned': 'warning',
            'accepted': 'primary',
            'at_store': 'info',
            'picked_up': 'info',
            'in_transit': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
            'failed': 'danger'
        }
        return status_colors.get(self.status, 'secondary')


class DeliveryTracking(TimeStampedModel):
    """Track delivery agent's location during delivery"""
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='tracking_points')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Location for {self.delivery.delivery_id} at {self.timestamp}"


class DeliveryIssue(TimeStampedModel):
    """Model to track delivery issues"""
    ISSUE_TYPES = [
        ('delay', 'Delivery Delay'),
        ('damage', 'Package Damage'),
        ('location', 'Wrong Location'),
        ('customer', 'Customer Unavailable'),
        ('traffic', 'Traffic Issues'),
        ('vehicle', 'Vehicle Problems'),
        ('weather', 'Bad Weather'),
        ('other', 'Other Issue'),
    ]
    
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='issues')
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPES)
    description = models.TextField()
    resolved = models.BooleanField(default=False)
    resolution = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.get_issue_type_display()} - {self.delivery.delivery_id}"


class DeliveryRating(TimeStampedModel):
    """Customer ratings for deliveries"""
    delivery = models.OneToOneField(Delivery, on_delete=models.CASCADE, related_name='rating')
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    feedback = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Rating for {self.delivery.delivery_id}: {self.rating}/5"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Update agent's average rating
        agent = self.delivery.agent
        ratings = DeliveryRating.objects.filter(delivery__agent=agent)
        total_ratings = ratings.count()
        
        if total_ratings > 0:
            avg_rating = sum(r.rating for r in ratings) / total_ratings
            agent.average_rating = round(avg_rating, 2)
            agent.save()


class DeliveryAgentZipCoverage(TimeStampedModel):
    """Manages which ZIP areas a delivery agent can serve"""
    
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='zip_coverages')
    zip_area = models.ForeignKey(ZipArea, on_delete=models.CASCADE, related_name='delivery_new_agent_coverages')
    is_active = models.BooleanField(default=True)
    
    # Optional: different delivery fees per area
    delivery_fee_override = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True,
                                               help_text="Override default delivery fee for this area")
    
    def __str__(self):
        return f"{self.agent.user.get_full_name()} serves {self.zip_area.zip_code}"
    
    class Meta:
        unique_together = ['agent', 'zip_area']
        ordering = ['zip_area__zip_code']
