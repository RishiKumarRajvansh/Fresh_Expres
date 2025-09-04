from django.contrib import admin
from .models import PaymentMethod, UPIProvider

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['user', 'payment_type', 'upi_id', 'card_number', 'is_default', 'is_active', 'created_at']
    list_filter = ['payment_type', 'is_default', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'upi_id', 'card_holder_name']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(UPIProvider)
class UPIProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
