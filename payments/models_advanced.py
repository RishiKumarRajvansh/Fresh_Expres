"""
Advanced Payment Integration System
Supports multiple payment gateways, digital wallets, and hyperlocal payment methods
"""
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from core.models import TimeStampedModel
from .models import PaymentMethod  # Import from basic models
import uuid
import hmac
import hashlib
import json

User = get_user_model()


class PaymentGateway(TimeStampedModel):
    """Configure multiple payment gateways"""
    GATEWAY_TYPES = [
        ('stripe', 'Stripe'),
        ('razorpay', 'Razorpay'),
        ('paytm', 'Paytm'),
        ('phonepe', 'PhonePe'),
        ('googlepay', 'Google Pay'),
        ('payu', 'PayU'),
        ('cashfree', 'Cashfree'),
        ('instamojo', 'Instamojo'),
    ]
    
    name = models.CharField(max_length=50)
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_TYPES)
    
    # Configuration
    api_key = models.CharField(max_length=500, help_text="Public/API Key")
    secret_key = models.CharField(max_length=500, help_text="Secret Key")
    merchant_id = models.CharField(max_length=100, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_sandbox = models.BooleanField(default=True)
    supports_recurring = models.BooleanField(default=False)
    supports_refunds = models.BooleanField(default=True)
    supports_webhooks = models.BooleanField(default=True)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100000.00)
    
    # Fee configuration
    fee_fixed = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Fixed fee per transaction")
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage fee")
    
    # Regional settings
    supported_currencies = models.JSONField(default=list, help_text="List of supported currency codes")
    supported_countries = models.JSONField(default=list, help_text="List of supported country codes")
    
    # Additional gateway-specific configuration
    additional_config = models.JSONField(default=dict, blank=True, help_text="Gateway-specific configuration")
    
    # Priority for gateway selection
    priority = models.PositiveIntegerField(default=10)
    
    class Meta:
        ordering = ['priority', 'name']
        unique_together = ['gateway_type', 'merchant_id']
    
    def __str__(self):
        return f"{self.name} ({self.gateway_type})"
    
    def calculate_fee(self, amount):
        """Calculate transaction fee for this gateway"""
        percentage_amount = (amount * self.fee_percentage) / 100
        return self.fee_fixed + percentage_amount
    
    def get_api_config(self):
        """Get API configuration for this gateway"""
        config = {
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            'merchant_id': self.merchant_id,
            'is_sandbox': self.is_sandbox
        }
        
        # Add gateway-specific configuration
        if hasattr(self, 'additional_config') and self.additional_config:
            if self.gateway_type == 'phonepe':
                config.update({
                    'salt_key': self.secret_key,  # For PhonePe, secret_key is the salt_key
                    'salt_index': self.additional_config.get('salt_index', 1),
                    'base_url': self.additional_config.get('base_url', 
                        'https://api-preprod.phonepe.com/apis/pg-sandbox' if self.is_sandbox 
                        else 'https://api.phonepe.com/apis/hermes'
                    )
                })
        
        return config


class PaymentTransaction(TimeStampedModel):
    """Track all payment transactions"""
    TRANSACTION_TYPES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('partial_refund', 'Partial Refund'),
        ('cancellation', 'Cancellation'),
        ('chargeback', 'Chargeback'),
    ]
    
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    # Unique transaction ID
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Associated order
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Payment details
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='payment')
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    
    # Amounts
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    gateway_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='INR')
    
    # Gateway response
    gateway_transaction_id = models.CharField(max_length=200, blank=True)
    gateway_response = models.JSONField(default=dict)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Retry handling
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['gateway_transaction_id']),
            models.Index(fields=['status', 'initiated_at']),
        ]
    
    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status} - ₹{self.amount}"
    
    def save(self, *args, **kwargs):
        # Calculate net amount
        if not self.net_amount:
            self.net_amount = self.amount - self.gateway_fee
        
        super().save(*args, **kwargs)
    
    def can_retry(self):
        """Check if transaction can be retried"""
        return (self.status == 'failed' and 
                self.retry_count < self.max_retries and
                (not self.expires_at or timezone.now() < self.expires_at))
    
    def mark_success(self, gateway_transaction_id=None, gateway_response=None):
        """Mark transaction as successful"""
        with transaction.atomic():
            self.status = 'success'
            self.completed_at = timezone.now()
            
            if gateway_transaction_id:
                self.gateway_transaction_id = gateway_transaction_id
            
            if gateway_response:
                self.gateway_response = gateway_response
            
            self.save()
            
            # Update order payment status
            from orders.models import Order
            order = Order.objects.select_for_update().get(id=self.order.id)
            order.payment_status = 'paid'
            order.paid_at = self.completed_at
            order.save()
    
    def mark_failed(self, error_message=None, gateway_response=None):
        """Mark transaction as failed"""
        self.status = 'failed'
        
        if error_message:
            self.notes = error_message
        
        if gateway_response:
            self.gateway_response = gateway_response
        
        self.save()
    
    def create_refund(self, refund_amount=None, reason=None):
        """Create a refund transaction"""
        if self.status != 'success':
            raise ValueError("Can only refund successful transactions")
        
        if refund_amount is None:
            refund_amount = self.amount
        
        if refund_amount > self.amount:
            raise ValueError("Refund amount cannot exceed transaction amount")
        
        refund_transaction = PaymentTransaction.objects.create(
            order=self.order,
            user=self.user,
            payment_method=self.payment_method,
            gateway=self.gateway,
            transaction_type='refund' if refund_amount == self.amount else 'partial_refund',
            amount=refund_amount,
            currency=self.currency,
            metadata={'parent_transaction': str(self.transaction_id), 'reason': reason}
        )
        
        return refund_transaction


class PaymentWebhook(TimeStampedModel):
    """Handle payment gateway webhooks"""
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    webhook_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100)
    
    # Raw webhook data
    raw_data = models.JSONField()
    headers = models.JSONField(default=dict)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Associated transaction (if applicable)
    transaction = models.ForeignKey(
        PaymentTransaction, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='webhooks'
    )
    
    # Error handling
    processing_error = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['gateway', 'webhook_id']
        indexes = [
            models.Index(fields=['gateway', 'is_processed']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.gateway.name} - {self.event_type} - {self.webhook_id}"
    
    def verify_signature(self, signature, secret_key):
        """Verify webhook signature"""
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            json.dumps(self.raw_data, sort_keys=True).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def process(self):
        """Process the webhook"""
        try:
            processor = PaymentWebhookProcessor(self)
            processor.process()
            
            self.is_processed = True
            self.processed_at = timezone.now()
            self.save()
            
        except Exception as e:
            self.processing_error = str(e)
            self.retry_count += 1
            self.save()
            raise


class PaymentAnalytics(TimeStampedModel):
    """Daily payment analytics"""
    date = models.DateField()
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    
    # Transaction counts
    total_transactions = models.PositiveIntegerField(default=0)
    successful_transactions = models.PositiveIntegerField(default=0)
    failed_transactions = models.PositiveIntegerField(default=0)
    
    # Amounts
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    successful_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Rates
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    average_transaction_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Payment method breakdown
    card_transactions = models.PositiveIntegerField(default=0)
    upi_transactions = models.PositiveIntegerField(default=0)
    wallet_transactions = models.PositiveIntegerField(default=0)
    netbanking_transactions = models.PositiveIntegerField(default=0)
    cod_transactions = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['date', 'gateway']
        ordering = ['-date', 'gateway']
    
    def __str__(self):
        return f"{self.date} - {self.gateway.name} Analytics"
    
    def calculate_metrics(self):
        """Calculate success rate and average transaction value"""
        if self.total_transactions > 0:
            self.success_rate = (self.successful_transactions / self.total_transactions) * 100
        
        if self.successful_transactions > 0:
            self.average_transaction_value = self.successful_amount / self.successful_transactions
        
        self.save()


class PaymentWebhookProcessor:
    """Process payment webhooks from different gateways"""
    
    def __init__(self, webhook):
        self.webhook = webhook
        self.gateway = webhook.gateway
        self.data = webhook.raw_data
    
    def process(self):
        """Process webhook based on gateway type"""
        processor_method = getattr(
            self, 
            f'process_{self.gateway.gateway_type}', 
            self.process_generic
        )
        processor_method()
    
    def process_stripe(self):
        """Process Stripe webhooks"""
        event_type = self.data.get('type')
        
        if event_type == 'payment_intent.succeeded':
            self._handle_payment_success()
        elif event_type == 'payment_intent.payment_failed':
            self._handle_payment_failure()
        elif event_type == 'charge.dispute.created':
            self._handle_chargeback()
    
    def process_razorpay(self):
        """Process Razorpay webhooks"""
        event_type = self.webhook.event_type
        
        if event_type == 'payment.captured':
            self._handle_payment_success()
        elif event_type == 'payment.failed':
            self._handle_payment_failure()
        elif event_type == 'refund.processed':
            self._handle_refund_success()
    
    def process_paytm(self):
        """Process Paytm webhooks"""
        # Implement Paytm-specific webhook processing
        pass
    
    def process_generic(self):
        """Generic webhook processing"""
        # Basic webhook processing for other gateways
        pass
    
    def _handle_payment_success(self):
        """Handle successful payment"""
        gateway_transaction_id = self._extract_transaction_id()
        
        try:
            transaction = PaymentTransaction.objects.get(
                gateway_transaction_id=gateway_transaction_id,
                gateway=self.gateway
            )
            transaction.mark_success(
                gateway_transaction_id=gateway_transaction_id,
                gateway_response=self.data
            )
            self.webhook.transaction = transaction
            
        except PaymentTransaction.DoesNotExist:
            pass  # Transaction not found, might be external payment
    
    def _handle_payment_failure(self):
        """Handle failed payment"""
        gateway_transaction_id = self._extract_transaction_id()
        error_message = self._extract_error_message()
        
        try:
            transaction = PaymentTransaction.objects.get(
                gateway_transaction_id=gateway_transaction_id,
                gateway=self.gateway
            )
            transaction.mark_failed(
                error_message=error_message,
                gateway_response=self.data
            )
            self.webhook.transaction = transaction
            
        except PaymentTransaction.DoesNotExist:
            pass
    
    def _handle_refund_success(self):
        """Handle successful refund"""
        # Implement refund processing logic
        pass
    
    def _handle_chargeback(self):
        """Handle chargeback/dispute"""
        # Implement chargeback processing logic
        pass
    
    def _extract_transaction_id(self):
        """Extract transaction ID from webhook data"""
        # This would vary by gateway
        if self.gateway.gateway_type == 'stripe':
            return self.data.get('data', {}).get('object', {}).get('id')
        elif self.gateway.gateway_type == 'razorpay':
            return self.data.get('payload', {}).get('payment', {}).get('entity', {}).get('id')
        
        return None
    
    def _extract_error_message(self):
        """Extract error message from webhook data"""
        if self.gateway.gateway_type == 'stripe':
            return self.data.get('data', {}).get('object', {}).get('last_payment_error', {}).get('message')
        elif self.gateway.gateway_type == 'razorpay':
            return self.data.get('payload', {}).get('payment', {}).get('entity', {}).get('error_description')
        
        return "Payment failed"
