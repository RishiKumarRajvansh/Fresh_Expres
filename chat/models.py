from django.db import models
from django.contrib.auth import get_user_model
from core.models import TimeStampedModel
from stores.models import Store
from orders.models import Order
import uuid

User = get_user_model()

class ChatSession(TimeStampedModel):
    """Chat sessions between customers and stores"""
    SESSION_STATUS = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated to Admin'),
    ]
    
    SESSION_TYPES = [
        ('general_inquiry', 'General Inquiry'),
        ('order_support', 'Order Support'),
        ('product_question', 'Product Question'),
        ('complaint', 'Complaint'),
    ]
    
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_chat_sessions')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='chat_sessions')
    
    # Optional order reference
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, blank=True, null=True, related_name='chat_sessions')
    
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='general_inquiry')
    status = models.CharField(max_length=15, choices=SESSION_STATUS, default='active')
    subject = models.CharField(max_length=200, blank=True, null=True)
    
    # Admin takeover
    taken_over_by_admin = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, 
        related_name='admin_taken_chat_sessions'
    )
    takeover_reason = models.TextField(blank=True, null=True)
    taken_over_at = models.DateTimeField(blank=True, null=True)
    
    # Session metadata
    last_message_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, 
        related_name='closed_chat_sessions'
    )
    
    # Customer satisfaction
    customer_rating = models.PositiveIntegerField(
        choices=[(i, i) for i in range(1, 6)], blank=True, null=True
    )
    customer_feedback = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Chat: {self.customer.username} <-> {self.store.name} ({str(self.session_id)[:8]})"
    
    @property
    def current_handler(self):
        """Returns who is currently handling this chat"""
        if self.taken_over_by_admin:
            return self.taken_over_by_admin
        return self.store.owner
    
    @property
    def unread_count_for_customer(self):
        return self.messages.filter(
            sender__in=[self.store.owner, self.taken_over_by_admin],
            is_read_by_customer=False
        ).count()
    
    @property
    def unread_count_for_store(self):
        return self.messages.filter(
            sender=self.customer,
            is_read_by_store=False
        ).count()
    
    class Meta:
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['store', 'status']),
            models.Index(fields=['status', 'last_message_at']),
        ]

class ChatMessage(TimeStampedModel):
    """Individual chat messages"""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System Message'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages')
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(blank=True, null=True)
    
    # File attachments
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    
    # Read status
    is_read_by_customer = models.BooleanField(default=False)
    is_read_by_store = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # System message metadata
    system_event = models.CharField(max_length=50, blank=True, null=True)
    system_data = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Message from {self.sender.username} in session {str(self.session.session_id)[:8]}"
    
    def save(self, *args, **kwargs):
        # Update session's last_message_at
        if self.pk is None:  # New message
            self.session.last_message_at = self.created_at or self.session.updated_at
            self.session.save()
        super().save(*args, **kwargs)
    
    @property
    def is_from_customer(self):
        return self.sender == self.session.customer
    
    @property
    def is_from_store(self):
        return self.sender == self.session.store.owner
    
    @property
    def is_from_admin(self):
        return self.sender == self.session.taken_over_by_admin
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]

class ChatNotification(TimeStampedModel):
    """Notifications for chat events"""
    NOTIFICATION_TYPES = [
        ('new_message', 'New Message'),
        ('session_started', 'Session Started'),
        ('session_closed', 'Session Closed'),
        ('admin_takeover', 'Admin Takeover'),
        ('customer_rating', 'Customer Rating'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_notifications')
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # Additional data for the notification
    metadata = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
    
    def mark_as_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['session', 'created_at']),
        ]

class ChatTemplate(TimeStampedModel):
    """Pre-defined message templates for quick responses"""
    TEMPLATE_CATEGORIES = [
        ('greeting', 'Greeting'),
        ('order_status', 'Order Status'),
        ('product_info', 'Product Information'),
        ('delivery_info', 'Delivery Information'),
        ('closing', 'Closing'),
        ('escalation', 'Escalation'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='chat_templates')
    category = models.CharField(max_length=20, choices=TEMPLATE_CATEGORIES)
    title = models.CharField(max_length=100)
    content = models.TextField()
    
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.store.name} - {self.title}"
    
    def increment_usage(self):
        self.usage_count += 1
        self.save()
    
    class Meta:
        ordering = ['category', 'title']
        unique_together = ['store', 'title']

class AutoResponse(TimeStampedModel):
    """Automated responses based on keywords or conditions"""
    TRIGGER_TYPES = [
        ('keyword', 'Keyword Match'),
        ('business_hours', 'Outside Business Hours'),
        ('order_status', 'Order Status Query'),
        ('first_message', 'First Message'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='auto_responses')
    trigger_type = models.CharField(max_length=15, choices=TRIGGER_TYPES)
    
    # Trigger conditions
    keywords = models.TextField(blank=True, null=True, help_text="Comma-separated keywords")
    conditions = models.JSONField(default=dict, blank=True, help_text="Additional conditions")
    
    # Response
    response_text = models.TextField()
    delay_seconds = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.store.name} - {self.get_trigger_type_display()}"
    
    class Meta:
        ordering = ['trigger_type', 'created_at']
