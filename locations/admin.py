from django.contrib import admin
from .models import ZipArea, Address

@admin.register(ZipArea)
class ZipAreaAdmin(admin.ModelAdmin):
    list_display = ('zip_code', 'city', 'state', 'is_active', 'created_at')
    list_filter = ('state', 'is_active', 'created_at')
    search_fields = ('zip_code', 'city', 'state')

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'address_type', 'city', 'state', 'is_default', 'created_at')
    list_filter = ('address_type', 'is_default', 'state', 'created_at')
    search_fields = ('user__username', 'address_line_1', 'city', 'zip_code')
