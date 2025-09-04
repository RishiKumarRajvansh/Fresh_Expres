from django.contrib import admin
from .models import Setting, SystemLog, FAQ, FAQCategory

# These admin classes are imported by admin_site.py
# Models are registered with the custom admin site, not the default Django admin

@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'is_active', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('key', 'description')

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('level', 'message', 'module', 'user_id', 'ip_address', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('message', 'module', 'ip_address')
    readonly_fields = ('created_at',)

# FAQ admin classes - only used by custom admin site
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}

class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_active', 'order', 'created_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('question', 'answer')
    list_editable = ('is_active', 'order')
