from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from core.models import TimeStampedModel
from stores.models import Store
from orders.models import Order
from locations.models import ZipArea
import uuid

User = get_user_model()

class DeliveryAgent(TimeStampedModel):
    """Delivery agents for stores"""
    AGENT_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_break', 'On Break'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
    ]
    
    VEHICLE_TYPES = [
        ('bicycle', 'Bicycle'),
        ('scooter', 'Scooter'),
        ('motorcycle', 'Motorcycle'),
        ('car', 'Car'),
        ('van', 'Van'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_agent_profile')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_agents')
    agent_id = models.CharField(max_length=20, unique=True)
    
    # Personal Information
    phone_number = models.CharField(max_length=15)
    emergency_contact = models.CharField(max_length=15, blank=True, null=True)
    
    # Vehicle Information
    vehicle_type = models.CharField(max_length=15, choices=VEHICLE_TYPES, default='scooter')
    vehicle_number = models.CharField(max_length=20)
    license_number = models.CharField(max_length=50)
    
    # Documents
    license_image = models.ImageField(upload_to='delivery_agents/licenses/', blank=True, null=True)
    vehicle_registration = models.ImageField(upload_to='delivery_agents/vehicles/', blank=True, null=True)
    profile_photo = models.ImageField(upload_to='delivery_agents/photos/', blank=True, null=True)
    
    # Status and Settings
    status = models.CharField(max_length=10, choices=AGENT_STATUS, default='inactive')
    is_available = models.BooleanField(default=False)
    max_concurrent_orders = models.PositiveIntegerField(default=3)
    
    # Location tracking
    current_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    last_location_update = models.DateTimeField(blank=True, null=True)
    
    # Performance metrics
    total_deliveries = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.agent_id} ({self.store.name})"
    
    @property
    def success_rate(self):
        if self.total_deliveries == 0:
            return 0
        return round((self.successful_deliveries / self.total_deliveries) * 100, 2)
    
    @property
    def current_orders_count(self):
        return self.assigned_orders.filter(
            order__status__in=['out_for_delivery']
        ).count()
    
    @property
    def can_take_order(self):
        return (
            self.is_available and 
            self.status == 'active' and 
            self.current_orders_count < self.max_concurrent_orders
        )
    
    class Meta:
        unique_together = ['store', 'agent_id']

class DeliveryAssignment(TimeStampedModel):
    """Assignment of orders to delivery agents"""
    ASSIGNMENT_STATUS = [
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_assignment')
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='assigned_orders')
    
    status = models.CharField(max_length=15, choices=ASSIGNMENT_STATUS, default='assigned')
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    picked_up_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    
    # Distance and time estimates
    estimated_distance_km = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    estimated_time_minutes = models.PositiveIntegerField(blank=True, null=True)
    actual_time_minutes = models.PositiveIntegerField(blank=True, null=True)
    
    # Notes
    agent_notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Assignment: Order {self.order.order_number} -> {self.agent.user.get_full_name()}"
    
    class Meta:
        ordering = ['-assigned_at']

class DeliveryTracking(TimeStampedModel):
    """Real-time tracking of deliveries"""
    assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.CASCADE, related_name='tracking_points')
    
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    
    # Additional tracking info
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    battery_level = models.PositiveIntegerField(blank=True, null=True)
    
    def __str__(self):
        return f"Tracking: {self.assignment.order.order_number} at {self.created_at}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['assignment', 'created_at']),
        ]

class ProofOfDelivery(TimeStampedModel):
    """Proof of delivery documentation"""
    DELIVERY_METHODS = [
        ('handed_to_customer', 'Handed to Customer'),
        ('left_at_door', 'Left at Door'),
        ('left_with_security', 'Left with Security'),
        ('left_with_neighbor', 'Left with Neighbor'),
    ]
    
    assignment = models.OneToOneField(DeliveryAssignment, on_delete=models.CASCADE, related_name='proof_of_delivery')
    
    # Delivery confirmation
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS, default='handed_to_customer')
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    
    # OTP verification
    otp_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    
    # Photo proof
    delivery_photo = models.ImageField(upload_to='delivery_proofs/', blank=True, null=True)
    signature_image = models.ImageField(upload_to='delivery_signatures/', blank=True, null=True)
    
    # Location confirmation
    delivery_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    delivery_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"POD: Order {self.assignment.order.order_number}"

class DeliveryRating(TimeStampedModel):
    """Customer ratings for delivery service"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_rating')
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='ratings')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delivery_ratings_given')
    
    # Ratings
    overall_rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    delivery_time_rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    packaging_rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    agent_behavior_rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    
    # Comments
    feedback = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Rating: {self.overall_rating}/5 for Order {self.order.order_number}"
    
    class Meta:
        unique_together = ['order', 'customer']

class DeliveryZone(TimeStampedModel):
    """Delivery zones for optimized routing"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_zones')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Zone boundaries (stored as JSON polygon)
    boundary_coordinates = models.JSONField(help_text="Array of [lat, lng] coordinates defining the zone boundary")
    
    # Zone settings
    priority_level = models.PositiveIntegerField(default=1)
    max_delivery_time_minutes = models.PositiveIntegerField(default=60)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"
    
    class Meta:
        unique_together = ['store', 'name']
        ordering = ['priority_level', 'name']


class DeliveryAgentZipCoverage(TimeStampedModel):
    """Manages which ZIP areas a delivery agent can serve"""
    
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='zip_coverages')
    zip_area = models.ForeignKey(ZipArea, on_delete=models.CASCADE, related_name='delivery_agent_coverages')
    is_active = models.BooleanField(default=True)
    
    # Optional: different delivery fees per area
    delivery_fee_override = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True,
                                               help_text="Override default delivery fee for this area")
    
    def __str__(self):
        return f"{self.agent.user.get_full_name()} serves {self.zip_area.zip_code}"
    
    class Meta:
        unique_together = ['agent', 'zip_area']
        ordering = ['zip_area__zip_code']
