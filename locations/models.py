from django.db import models
from decimal import Decimal
from core.models import TimeStampedModel

class ZipArea(TimeStampedModel):
    """ZIP code areas for delivery coverage"""
    zip_code = models.CharField(max_length=10, unique=True, db_index=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='India')
    
    # Default delivery settings for this ZIP
    default_delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    default_min_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    default_delivery_time_minutes = models.PositiveIntegerField(default=60)
    
    # Geographical coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.zip_code} - {self.city}, {self.state}"
    
    class Meta:
        ordering = ['state', 'city', 'zip_code']
        indexes = [
            models.Index(fields=['zip_code', 'is_active']),
            models.Index(fields=['city', 'state']),
        ]

class Address(TimeStampedModel):
    """User addresses"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='home')
    
    # Address fields
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    landmark = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    
    # Geographical coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Contact information
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=15, blank=True, null=True)
    
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.label} - {self.address_line_1}, {self.city}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def full_address(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        if self.landmark:
            parts.append(f"Near {self.landmark}")
        parts.extend([self.city, self.state, self.zip_code])
        return ", ".join(parts)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name_plural = "Addresses"
