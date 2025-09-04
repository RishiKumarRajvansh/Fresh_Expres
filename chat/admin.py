from django.contrib import admin
from .models import ChatSession, ChatMessage, ChatNotification, AutoResponse, ChatTemplate

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'store', 'status', 'last_message_at', 'created_at')
    list_filter = ('status', 'store', 'created_at', 'last_message_at')
    search_fields = ('customer__username', 'store__name')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'sender', 'message_type', 'created_at')
    list_filter = ('message_type', 'created_at', 'session__store')
    search_fields = ('session__customer__username', 'message', 'sender__username')

@admin.register(ChatNotification)
class ChatNotificationAdmin(admin.ModelAdmin):
    list_display = ('session', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('session__customer__username', 'recipient__username')

@admin.register(AutoResponse)
class AutoResponseAdmin(admin.ModelAdmin):
    list_display = ('store', 'trigger_type', 'is_active', 'created_at')
    list_filter = ('trigger_type', 'is_active', 'store', 'created_at')
    search_fields = ('keywords', 'response_text', 'store__name')

@admin.register(ChatTemplate)
class ChatTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'store', 'is_active', 'usage_count', 'created_at')
    list_filter = ('category', 'is_active', 'store', 'created_at')
    search_fields = ('title', 'content', 'store__name')
