"""
Real-time Inventory Synchronization System
Handles cross-store inventory visibility, automatic stock transfers, and real-time updates
"""
from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import logging
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


class InventorySyncEvent(TimeStampedModel):
    """Track all inventory synchronization events"""
    EVENT_TYPES = [
        ('stock_update', 'Stock Update'),
        ('transfer_request', 'Transfer Request'),
        ('transfer_complete', 'Transfer Complete'),
        ('restock_alert', 'Restock Alert'),
        ('low_stock_warning', 'Low Stock Warning'),
        ('out_of_stock', 'Out of Stock'),
    ]
    
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    store = models.ForeignKey('stores.Store', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    
    # Stock levels
    previous_quantity = models.PositiveIntegerField(default=0)
    new_quantity = models.PositiveIntegerField(default=0)
    
    # Event details
    reason = models.CharField(max_length=200)
    triggered_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    
    # Related transfer
    transfer = models.ForeignKey('InterStoreTransfer', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'store', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]


class InterStoreTransfer(TimeStampedModel):
    """Manage inventory transfers between stores"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    
    # Transfer details
    from_store = models.ForeignKey('stores.Store', on_delete=models.CASCADE, related_name='transfers_out')
    to_store = models.ForeignKey('stores.Store', on_delete=models.CASCADE, related_name='transfers_in')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    
    # Quantities
    requested_quantity = models.PositiveIntegerField()
    approved_quantity = models.PositiveIntegerField(null=True, blank=True)
    transferred_quantity = models.PositiveIntegerField(default=0)
    
    # Status tracking
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')
    
    # Approval workflow
    requested_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='requested_transfers')
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Transfer notes
    request_reason = models.TextField()
    approval_notes = models.TextField(blank=True)
    completion_notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Transfer {self.id}: {self.product.name} ({self.from_store.name} → {self.to_store.name})"
    
    def approve(self, user, approved_qty=None, notes=""):
        """Approve the transfer request"""
        with transaction.atomic():
            self.status = 'approved'
            self.approved_by = user
            self.approved_at = timezone.now()
            self.approved_quantity = approved_qty or self.requested_quantity
            self.approval_notes = notes
            self.save()
            
            # Create sync events
            InventorySyncEvent.objects.create(
                product=self.product,
                store=self.from_store,
                event_type='transfer_request',
                new_quantity=self.approved_quantity,
                reason=f"Transfer approved to {self.to_store.name}",
                triggered_by=user,
                transfer=self
            )
    
    def complete(self, user, actual_qty=None, notes=""):
        """Mark transfer as completed"""
        with transaction.atomic():
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.transferred_quantity = actual_qty or self.approved_quantity
            self.completion_notes = notes
            self.save()
            
            # Update inventory
            from .services_inventory import InventorySyncService
            InventorySyncService.process_transfer_completion(self, user)


class StockAlert(TimeStampedModel):
    """Track stock alerts and restock notifications"""
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('restock_needed', 'Restock Needed'),
        ('excess_stock', 'Excess Stock'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    store = models.ForeignKey('stores.Store', on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=15, choices=ALERT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Stock information
    current_stock = models.PositiveIntegerField()
    threshold_level = models.PositiveIntegerField()
    recommended_restock = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    acknowledged_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Action taken
    action_taken = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def acknowledge(self, user, action_note=""):
        """Acknowledge the alert"""
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.action_taken = action_note
        self.save()
    
    def resolve(self):
        """Mark alert as resolved"""
        self.is_active = False
        self.resolved_at = timezone.now()
        self.save()
    
    class Meta:
        unique_together = ['product', 'store', 'alert_type']
        ordering = ['-priority', '-created_at']


class InventorySnapshot(models.Model):
    """Daily inventory snapshots for analytics"""
    store = models.ForeignKey('stores.Store', on_delete=models.CASCADE)
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    
    # Snapshot data
    snapshot_date = models.DateField()
    opening_stock = models.PositiveIntegerField()
    closing_stock = models.PositiveIntegerField()
    
    # Movement data
    stock_in = models.PositiveIntegerField(default=0)  # Restocks, transfers in
    stock_out = models.PositiveIntegerField(default=0)  # Sales, transfers out
    adjustments = models.IntegerField(default=0)  # Manual adjustments
    
    # Performance metrics
    turnover_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    days_of_stock = models.PositiveIntegerField(default=0)
    
    # Pricing
    average_selling_price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        unique_together = ['store', 'product', 'snapshot_date']
        indexes = [
            models.Index(fields=['snapshot_date', 'store']),
            models.Index(fields=['product', 'snapshot_date']),
        ]


class PredictiveRestockRule(TimeStampedModel):
    """Rules for predictive restocking algorithms"""
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    store = models.ForeignKey('stores.Store', on_delete=models.CASCADE)
    
    # Thresholds
    minimum_stock_level = models.PositiveIntegerField()
    reorder_level = models.PositiveIntegerField()
    maximum_stock_level = models.PositiveIntegerField()
    
    # Demand patterns
    avg_daily_demand = models.DecimalField(max_digits=8, decimal_places=2)
    seasonal_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('1.00'))
    lead_time_days = models.PositiveIntegerField(default=1)
    
    # Algorithm settings
    safety_stock_days = models.PositiveIntegerField(default=2)
    demand_variance = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.20'))
    
    # Status
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def calculate_reorder_quantity(self):
        """Calculate optimal reorder quantity"""
        safety_stock = self.avg_daily_demand * self.safety_stock_days
        reorder_qty = (self.avg_daily_demand * self.lead_time_days) + safety_stock
        return int(reorder_qty * self.seasonal_multiplier)
    
    class Meta:
        unique_together = ['product', 'store']
