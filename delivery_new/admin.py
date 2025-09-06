from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import DeliveryAgent, Delivery, DeliveryTracking, DeliveryIssue, DeliveryRating
from .models_settings import DeliverySettings


@admin.register(DeliveryAgent)
class DeliveryAgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent_id', 'user_link', 'get_name', 'get_phone', 'status', 'is_available', 
                    'total_deliveries', 'successful_deliveries', 'average_rating')
    list_filter = ('status', 'is_available', 'vehicle_type')
    search_fields = ('agent_id', 'user__username', 'user__email', 'phone_number')
    readonly_fields = ('agent_id', 'total_deliveries', 'successful_deliveries', 'average_rating',
                      'last_location_update')
    
    fieldsets = (
        ('Agent Information', {
            'fields': ('user', 'agent_id', 'store')
        }),
        ('Contact Details', {
            'fields': ('phone_number', 'alternative_phone')
        }),
        ('Status & Availability', {
            'fields': ('status', 'is_available', 'max_concurrent_orders', 'service_area_radius')
        }),
        ('Vehicle Information', {
            'fields': ('vehicle_type', 'vehicle_number')
        }),
        ('Location', {
            'fields': ('current_latitude', 'current_longitude', 'last_location_update')
        }),
        ('Performance Metrics', {
            'fields': ('total_deliveries', 'successful_deliveries', 'average_rating')
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    get_name.short_description = 'Name'
    
    def get_phone(self, obj):
        return obj.phone_number
    get_phone.short_description = 'Phone'


class DeliveryTrackingInline(admin.TabularInline):
    model = DeliveryTracking
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('timestamp', 'latitude', 'longitude')
    
    
class DeliveryIssueInline(admin.TabularInline):
    model = DeliveryIssue
    extra = 0
    readonly_fields = ('created_at',)
    

class DeliveryRatingInline(admin.TabularInline):
    model = DeliveryRating
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery_id', 'order_link', 'agent_link', 'status', 'created_at', 
                   'delivered_at', 'customer_name', 'store_name')
    list_filter = ('status', 'created_at', 'delivered_at')
    search_fields = ('delivery_id', 'order__order_number', 
                    'order__user__username', 'order__user__email')
    readonly_fields = ('delivery_id', 'created_at', 'assigned_at', 'accepted_at', 
                      'arrived_at_store_at', 'picked_up_at', 'delivered_at',
                      'store_pickup_otp', 'customer_delivery_otp')
    inlines = [DeliveryTrackingInline, DeliveryIssueInline, DeliveryRatingInline]
    
    fieldsets = (
        ('Delivery Information', {
            'fields': ('delivery_id', 'order', 'agent', 'status')
        }),
        ('OTP Verification', {
            'fields': ('store_pickup_otp', 'customer_delivery_otp', 'store_pickup_verified', 'customer_delivery_verified')
        }),
        ('Financial Details', {
            'fields': ('agent_payout', 'delivery_fee')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'assigned_at', 'accepted_at', 'arrived_at_store_at',
                      'picked_up_at', 'delivered_at')
        }),
    )
    
    def order_link(self, obj):
        if obj.order:
            url = reverse('admin:orders_order_change', args=[obj.order.id])
            return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
        return "-"
    order_link.short_description = 'Order'
    
    def agent_link(self, obj):
        if obj.agent:
            url = reverse('admin:delivery_new_deliveryagent_change', args=[obj.agent.id])
            return format_html('<a href="{}">{}</a>', url, obj.agent.user.username)
        return "-"
    agent_link.short_description = 'Agent'
    
    def customer_name(self, obj):
        if obj.order and obj.order.user:
            return f"{obj.order.user.first_name} {obj.order.user.last_name}"
        return "-"
    customer_name.short_description = 'Customer'
    
    def store_name(self, obj):
        if obj.order and hasattr(obj.order, 'store') and obj.order.store:
            return obj.order.store.name
        return "-"
    store_name.short_description = 'Store'


@admin.register(DeliveryIssue)
class DeliveryIssueAdmin(admin.ModelAdmin):
    list_display = ('id', 'delivery_link', 'issue_type', 'created_at', 'resolved')
    list_filter = ('issue_type', 'resolved', 'created_at')
    search_fields = ('delivery__delivery_id', 'description')
    readonly_fields = ('created_at',)
    
    def delivery_link(self, obj):
        url = reverse('admin:delivery_new_delivery_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.delivery_id)
    delivery_link.short_description = 'Delivery'


@admin.register(DeliveryRating)
class DeliveryRatingAdmin(admin.ModelAdmin):
    list_display = ('id', 'delivery_link', 'agent_name', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('delivery__delivery_id', 'feedback')
    readonly_fields = ('created_at',)
    
    def delivery_link(self, obj):
        url = reverse('admin:delivery_new_delivery_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.delivery_id)
    delivery_link.short_description = 'Delivery'
    
    def agent_name(self, obj):
        """Get the name of the delivery agent"""
        if obj.delivery and obj.delivery.agent and obj.delivery.agent.user:
            user = obj.delivery.agent.user
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return "-"
    agent_name.short_description = 'Agent'


@admin.register(DeliverySettings)
class DeliverySettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'calculation_method', 'base_delivery_fee', 'fee_per_km', 'free_delivery_threshold')
    fieldsets = (
        ('Basic Fee Settings', {
            'fields': ('calculation_method', 'base_delivery_fee')
        }),
        ('Distance-Based Settings', {
            'fields': ('fee_per_km',),
            'classes': ('collapse',),
        }),
        ('Fee Constraints', {
            'fields': ('minimum_delivery_fee', 'maximum_delivery_fee', 'free_delivery_threshold'),
        }),
        ('Agent Payouts', {
            'fields': ('agent_payout_percentage',),
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance of delivery settings
        return DeliverySettings.objects.count() == 0
    
    def agent_name(self, obj):
        if obj.delivery and obj.delivery.agent:
            return f"{obj.delivery.agent.user.first_name} {obj.delivery.agent.user.last_name}".strip() or obj.delivery.agent.user.username
        return "-"
    agent_name.short_description = 'Agent'
