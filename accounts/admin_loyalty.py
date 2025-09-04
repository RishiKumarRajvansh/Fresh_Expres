"""
Admin interface for Loyalty and Rewards System
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    LoyaltyProgram, UserLoyaltyAccount, LoyaltyTransaction,
    ReferralProgram, LoyaltyReward, UserRewardRedemption
)

@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'points_per_rupee', 'min_points_to_redeem', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UserLoyaltyAccount)
class UserLoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'available_points', 'current_tier', 'lifetime_earned', 'lifetime_redeemed')
    list_filter = ('current_tier', 'loyalty_program', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total_points', 'lifetime_earned', 'lifetime_redeemed', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'loyalty_program')

class LoyaltyTransactionInline(admin.TabularInline):
    model = LoyaltyTransaction
    extra = 0
    readonly_fields = ('transaction_type', 'points', 'reason', 'balance_after', 'created_at')
    can_delete = False

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('user_account', 'transaction_type', 'points', 'reason', 'balance_after', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user_account__user__username', 'reason')
    readonly_fields = ('balance_after', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_account__user', 'order')

@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred', 'referrer_bonus_given', 'referred_bonus_given', 'bonus_awarded_at', 'created_at')
    list_filter = ('referrer_bonus_given', 'referred_bonus_given', 'created_at')
    search_fields = ('referrer__username', 'referred__username')
    readonly_fields = ('bonus_awarded_at', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('referrer', 'referred', 'referred_first_order')

@admin.register(LoyaltyReward)
class LoyaltyRewardAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward_type', 'points_required', 'current_redemptions', 'is_available', 'valid_until')
    list_filter = ('reward_type', 'is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('current_redemptions', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'reward_type', 'points_required')
        }),
        ('Reward Value', {
            'fields': ('discount_amount', 'discount_percentage'),
            'description': 'Set either discount amount (fixed) or discount percentage'
        }),
        ('Availability', {
            'fields': ('is_active', 'max_redemptions_per_user', 'total_redemptions_allowed', 'current_redemptions')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def is_available(self, obj):
        if obj.is_available:
            return format_html('<span style="color: green;">✓ Available</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Available</span>')
    is_available.short_description = 'Status'

@admin.register(UserRewardRedemption)
class UserRewardRedemptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'reward', 'coupon_code', 'points_used', 'is_used', 'used_at', 'created_at')
    list_filter = ('is_used', 'reward__reward_type', 'created_at')
    search_fields = ('user__username', 'coupon_code', 'reward__title')
    readonly_fields = ('coupon_code', 'points_used', 'used_at', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'reward', 'order')
