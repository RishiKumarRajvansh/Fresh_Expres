from django.contrib import admin
from .models import (
    DeliveryAgent, DeliveryAssignment, DeliveryTracking, 
    ProofOfDelivery, DeliveryZone, DeliveryRating
)

@admin.register(DeliveryAgent)
class DeliveryAgentAdmin(admin.ModelAdmin):
    list_display = ('user', 'agent_id', 'status', 'store', 'is_available', 'created_at')
    list_filter = ('status', 'is_available', 'store', 'created_at')
    search_fields = ('user__username', 'agent_id', 'phone_number')

@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'agent', 'status', 'assigned_at', 'delivered_at')
    list_filter = ('status', 'assigned_at', 'delivered_at')
    search_fields = ('order__order_number', 'agent__user__username')

@admin.register(DeliveryTracking)
class DeliveryTrackingAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'latitude', 'longitude', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('assignment__order__order_number', 'assignment__agent__user__username')

@admin.register(ProofOfDelivery)
class ProofOfDeliveryAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'delivery_method', 'otp_verified', 'created_at')
    list_filter = ('delivery_method', 'otp_verified', 'created_at')
    search_fields = ('assignment__order__order_number', 'customer_name')

@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'priority_level', 'is_active', 'created_at')
    list_filter = ('is_active', 'store', 'created_at')
    search_fields = ('name', 'description', 'store__name')

@admin.register(DeliveryRating)
class DeliveryRatingAdmin(admin.ModelAdmin):
    list_display = ('order', 'agent', 'overall_rating', 'created_at')
    list_filter = ('overall_rating', 'created_at')
    search_fields = ('order__order_number', 'feedback')
