"""
Push Notification System for Real-time Customer Engagement
Handles web push notifications, user subscriptions, and notification campaigns
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
from core.models import TimeStampedModel
import json

User = get_user_model()


class PushSubscription(TimeStampedModel):
    """Store push notification subscriptions for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=500)
    p256dh_key = models.CharField(max_length=128)
    auth_key = models.CharField(max_length=32)
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Subscription preferences
    order_updates = models.BooleanField(default=True, help_text="Receive order status updates")
    delivery_updates = models.BooleanField(default=True, help_text="Receive delivery tracking updates")
    stock_alerts = models.BooleanField(default=False, help_text="Receive stock availability alerts")
    promotional = models.BooleanField(default=False, help_text="Receive promotional offers")
    store_updates = models.BooleanField(default=True, help_text="Receive store-specific updates")
    
    class Meta:
        unique_together = ['user', 'endpoint']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Push Subscription"
    
    def to_subscription_info(self):
        """Convert to format required by web push libraries"""
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh_key,
                'auth': self.auth_key
            }
        }


class NotificationTemplate(TimeStampedModel):
    """Pre-defined notification templates for different types of notifications"""
    NOTIFICATION_TYPES = [
        ('order_confirmed', 'Order Confirmed'),
        ('order_preparing', 'Order Being Prepared'),
        ('order_ready', 'Order Ready for Pickup'),
        ('order_out_for_delivery', 'Order Out for Delivery'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('delivery_assigned', 'Delivery Agent Assigned'),
        ('delivery_nearby', 'Delivery Agent Nearby'),
        ('stock_available', 'Product Back in Stock'),
        ('stock_low', 'Low Stock Alert'),
        ('price_drop', 'Price Drop Alert'),
        ('promotional', 'Promotional Offer'),
        ('store_closing', 'Store Closing Soon'),
        ('new_product', 'New Product Available'),
        ('loyalty_reward', 'Loyalty Points Earned'),
        ('payment_reminder', 'Payment Reminder'),
    ]
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, unique=True)
    title_template = models.CharField(max_length=100, help_text="Use {variables} for dynamic content")
    body_template = models.TextField(help_text="Use {variables} for dynamic content")
    icon_url = models.URLField(default='/static/img/icon-192x192.png')
    
    # Action buttons
    primary_action_text = models.CharField(max_length=50, blank=True)
    primary_action_url = models.CharField(max_length=200, blank=True)
    secondary_action_text = models.CharField(max_length=50, blank=True)
    secondary_action_url = models.CharField(max_length=200, blank=True)
    
    # Behavior settings
    require_interaction = models.BooleanField(default=False)
    silent = models.BooleanField(default=False)
    tag = models.CharField(max_length=50, blank=True, help_text="Groups related notifications")
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.get_notification_type_display()} Template"
    
    def render_notification(self, context=None):
        """Render notification with context variables"""
        if context is None:
            context = {}
        
        title = self.title_template.format(**context)
        body = self.body_template.format(**context)
        
        notification_data = {
            'title': title,
            'body': body,
            'icon': self.icon_url,
            'tag': self.tag or self.notification_type,
            'requireInteraction': self.require_interaction,
            'silent': self.silent,
            'data': {
                'type': self.notification_type,
                'url': context.get('url', '/'),
                **context
            }
        }
        
        # Add actions if defined
        actions = []
        if self.primary_action_text and self.primary_action_url:
            actions.append({
                'action': 'primary',
                'title': self.primary_action_text,
                'url': self.primary_action_url.format(**context) if context else self.primary_action_url
            })
        
        if self.secondary_action_text and self.secondary_action_url:
            actions.append({
                'action': 'secondary',
                'title': self.secondary_action_text,
                'url': self.secondary_action_url.format(**context) if context else self.secondary_action_url
            })
        
        if actions:
            notification_data['actions'] = actions
        
        return notification_data


class NotificationCampaign(TimeStampedModel):
    """Manage notification campaigns for bulk messaging"""
    CAMPAIGN_STATUS = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    TARGETING_TYPES = [
        ('all_users', 'All Users'),
        ('active_users', 'Active Users (last 30 days)'),
        ('new_users', 'New Users (last 7 days)'),
        ('location_based', 'Location Based'),
        ('purchase_history', 'Based on Purchase History'),
        ('loyalty_tier', 'Based on Loyalty Tier'),
        ('custom_segment', 'Custom User Segment'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    
    # Targeting
    targeting_type = models.CharField(max_length=20, choices=TARGETING_TYPES)
    targeting_criteria = JSONField(default=dict, help_text="Additional targeting criteria")
    
    # Scheduling
    status = models.CharField(max_length=15, choices=CAMPAIGN_STATUS, default='draft')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    target_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def delivery_rate(self):
        """Calculate delivery rate percentage"""
        if self.sent_count > 0:
            return (self.delivered_count / self.sent_count) * 100
        return 0
    
    @property
    def click_rate(self):
        """Calculate click-through rate percentage"""
        if self.delivered_count > 0:
            return (self.clicked_count / self.delivered_count) * 100
        return 0


class NotificationLog(TimeStampedModel):
    """Log individual notification deliveries"""
    DELIVERY_STATUS = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('clicked', 'Clicked'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE)
    campaign = models.ForeignKey(NotificationCampaign, on_delete=models.CASCADE, null=True, blank=True)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    
    # Notification content
    title = models.CharField(max_length=100)
    body = models.TextField()
    notification_data = JSONField(default=dict)
    
    # Delivery tracking
    status = models.CharField(max_length=15, choices=DELIVERY_STATUS, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['status', 'sent_at']),
        ]
    
    def __str__(self):
        return f"Notification to {self.user.username}: {self.title[:50]}"


class NotificationPreference(TimeStampedModel):
    """User-specific notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Global preferences
    push_notifications_enabled = models.BooleanField(default=True)
    email_notifications_enabled = models.BooleanField(default=True)
    sms_notifications_enabled = models.BooleanField(default=False)
    
    # Category preferences
    order_notifications = models.BooleanField(default=True)
    delivery_notifications = models.BooleanField(default=True)
    promotional_notifications = models.BooleanField(default=False)
    stock_notifications = models.BooleanField(default=False)
    store_notifications = models.BooleanField(default=True)
    loyalty_notifications = models.BooleanField(default=True)
    
    # Timing preferences
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(default='22:00:00')
    quiet_hours_end = models.TimeField(default='08:00:00')
    
    # Frequency controls
    max_promotional_per_day = models.PositiveIntegerField(default=2)
    max_stock_alerts_per_day = models.PositiveIntegerField(default=5)
    
    def __str__(self):
        return f"{self.user.username} - Notification Preferences"
    
    def is_quiet_hours(self, check_time=None):
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled:
            return False
        
        if check_time is None:
            check_time = timezone.localtime().time()
        
        start_time = self.quiet_hours_start
        end_time = self.quiet_hours_end
        
        # Handle overnight quiet hours (e.g., 10 PM to 8 AM)
        if start_time > end_time:
            return check_time >= start_time or check_time <= end_time
        else:
            return start_time <= check_time <= end_time
    
    def can_send_notification(self, notification_type, check_promotional_limits=True):
        """Check if user can receive a specific type of notification"""
        # Check global preference
        if not self.push_notifications_enabled:
            return False
        
        # Check quiet hours for non-urgent notifications
        urgent_types = ['order_confirmed', 'order_delivered', 'delivery_assigned']
        if notification_type not in urgent_types and self.is_quiet_hours():
            return False
        
        # Check category preferences
        category_mapping = {
            'order_confirmed': self.order_notifications,
            'order_preparing': self.order_notifications,
            'order_ready': self.order_notifications,
            'order_out_for_delivery': self.delivery_notifications,
            'order_delivered': self.delivery_notifications,
            'delivery_assigned': self.delivery_notifications,
            'promotional': self.promotional_notifications,
            'stock_available': self.stock_notifications,
            'store_closing': self.store_notifications,
            'loyalty_reward': self.loyalty_notifications,
        }
        
        if notification_type in category_mapping:
            if not category_mapping[notification_type]:
                return False
        
        # Check daily limits for promotional notifications
        if check_promotional_limits and notification_type == 'promotional':
            today_promotional_count = NotificationLog.objects.filter(
                user=self.user,
                template__notification_type='promotional',
                sent_at__date=timezone.now().date(),
                status__in=['sent', 'delivered']
            ).count()
            
            if today_promotional_count >= self.max_promotional_per_day:
                return False
        
        return True
