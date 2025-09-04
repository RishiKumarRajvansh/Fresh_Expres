from django.contrib import admin
from .models import Store, StoreZipCoverage, StoreClosureRequest, DeliverySlot

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'store_code', 'owner', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'store_code', 'owner__username', 'address')
    readonly_fields = ('store_code', 'created_at', 'updated_at')

@admin.register(StoreZipCoverage)
class StoreZipCoverageAdmin(admin.ModelAdmin):
    list_display = ('store', 'zip_area', 'delivery_fee', 'min_order_value', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('store__name', 'zip_area__zip_code')

@admin.register(StoreClosureRequest)
class StoreClosureRequestAdmin(admin.ModelAdmin):
    list_display = ('store', 'reason', 'status', 'created_at', 'approved_by')
    list_filter = ('status', 'created_at')
    search_fields = ('store__name', 'reason')

@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ('store', 'start_time', 'end_time', 'is_active', 'max_orders')
    list_filter = ('is_active', 'store')
    search_fields = ('store__name',)
