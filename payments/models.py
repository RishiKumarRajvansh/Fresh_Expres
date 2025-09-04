from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
# from orders.models import Order  # Will uncomment when ready

User = get_user_model()

class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('upi', 'UPI Payment'),
        ('card', 'Credit/Debit Card'),
        ('cod', 'Cash on Delivery'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Digital Wallet'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    
    # For UPI
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    
    # For Cards
    card_number = models.CharField(max_length=20, blank=True, null=True)  # Encrypted
    card_holder_name = models.CharField(max_length=100, blank=True, null=True)
    expiry_month = models.CharField(max_length=2, blank=True, null=True)
    expiry_year = models.CharField(max_length=4, blank=True, null=True)
    card_type = models.CharField(max_length=20, blank=True, null=True)  # visa, mastercard, etc.
    
    # Common fields
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.payment_type == 'upi':
            return f'UPI: {self.upi_id}'
        elif self.payment_type == 'card':
            return f'Card: ****{self.card_number[-4:] if self.card_number else ""}'
        elif self.payment_type == 'cod':
            return 'Cash on Delivery'
        return self.get_payment_type_display()

# Payment model will be added once Order model is properly set up

class UPIProvider(models.Model):
    """Supported UPI providers"""
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)  # gpay, phonepe, paytm, etc.
    icon = models.ImageField(upload_to='upi_icons/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
