from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from core.models import TimeStampedModel
from locations.models import ZipArea
import uuid

User = get_user_model()

class Store(TimeStampedModel):
    """Store model for multi-store platform"""
    STORE_STATUS = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('pending_approval', 'Pending Approval'),
        ('suspended', 'Suspended'),
    ]
    
    # Basic Information
    store_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store_code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    # Owner
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_stores')
    
    # Contact Information
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)
    
    # Branding
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='store_banners/', blank=True, null=True)
    
    # Business Hours (stored as JSON for flexibility)
    business_hours = models.JSONField(default=dict, blank=True)
    
    # Status and Settings
    status = models.CharField(max_length=20, choices=STORE_STATUS, default='pending_approval')
    is_active = models.BooleanField(default=True)
    auto_accept_orders = models.BooleanField(default=False)
    
    # Financial Information
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    
    # ZIP code coverage
    zip_coverage = models.ManyToManyField(ZipArea, through='StoreZipCoverage')
    
    def __str__(self):
        return f"{self.name} ({self.store_code})"
    
    @property
    def is_open(self):
        from django.utils import timezone
        from datetime import datetime, time
        import json
        
        if self.status != 'open':
            return False
        
        # Check if store has closure requests
        active_closure = self.closure_requests.filter(
            status='approved',
            requested_until__gt=timezone.now()
        ).exists()
        
        if active_closure:
            return False
        
        # Check business hours
        now = timezone.now()
        weekday = now.strftime('%A').lower()
        
        if self.business_hours and weekday in self.business_hours:
            hours = self.business_hours[weekday]
            
            # Check if store has opening/closing times for today
            if 'open' in hours and 'close' in hours:
                try:
                    open_time = datetime.strptime(hours['open'], '%H:%M').time()
                    close_time = datetime.strptime(hours['close'], '%H:%M').time()
                    current_time = now.time()
                    
                    # Check if current time is within business hours
                    if open_time <= current_time <= close_time:
                        return True
                except (ValueError, TypeError):
                    # If there's an error parsing times, assume closed
                    pass
            
            # Fallback to is_open flag if present
            elif hours.get('is_open', False):
                return True
        
        # If no business hours defined, assume always open (for testing)
        if not self.business_hours:
            return True
        
        return False
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['store_code', 'status']),
            models.Index(fields=['status', 'is_active']),
        ]

class StoreZipCoverage(TimeStampedModel):
    """Store coverage for specific ZIP codes with custom settings"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='zip_coverages')
    zip_area = models.ForeignKey(ZipArea, on_delete=models.CASCADE, related_name='store_coverages')
    
    # Override settings for this ZIP
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    min_order_value = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    delivery_time_minutes = models.PositiveIntegerField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    def get_delivery_fee(self):
        return self.delivery_fee or self.zip_area.default_delivery_fee
    
    def get_min_order_value(self):
        return self.min_order_value or self.zip_area.default_min_order_value
    
    def get_delivery_time(self):
        return self.delivery_time_minutes or self.zip_area.default_delivery_time_minutes
    
    def __str__(self):
        return f"{self.store.name} -> {self.zip_area.zip_code}"
    
    class Meta:
        unique_together = ['store', 'zip_area']

class StoreClosureRequest(TimeStampedModel):
    """Store closure requests for admin approval"""
    CLOSURE_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='closure_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    requested_until = models.DateTimeField()
    
    status = models.CharField(max_length=10, choices=CLOSURE_STATUS, default='pending')
    admin_notes = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='approved_closures')
    approved_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"Closure Request: {self.store.name} - {self.get_status_display()}"
    
    class Meta:
        ordering = ['-created_at']

class DeliverySlot(TimeStampedModel):
    """Delivery time slots for stores"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_slots')
    zip_area = models.ForeignKey(ZipArea, on_delete=models.CASCADE)
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_orders = models.PositiveIntegerField(default=10)
    is_express = models.BooleanField(default=False)
    express_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        express_text = " (Express)" if self.is_express else ""
        return f"{self.store.name} - {self.start_time}-{self.end_time}{express_text}"
    
    class Meta:
        ordering = ['start_time']
