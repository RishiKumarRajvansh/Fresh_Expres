from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, OTPVerification, Wishlist, ReferralProgram,
    UserLoyaltyAccount, LoyaltyTransaction, LoyaltyReward,
    LoyaltyConfiguration, PromotionalBanner
)

User = get_user_model()

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone_number', 'user_type', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'user_type', 'phone_verified')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'user_type')
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'loyalty_points', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_type', 'is_verified', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'otp_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    readonly_fields = ('created_at',)

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'store_product', 'added_at')
    list_filter = ('added_at', 'store_product__store')
    search_fields = ('user__username', 'store_product__product__name', 'store_product__store__name')
    readonly_fields = ('added_at',)
    raw_id_fields = ('user', 'store_product')
    
    def get_queryset(self, request):
        """Allow superusers to see all wishlists"""
        return super().get_queryset(request).select_related('user', 'store_product__product', 'store_product__store')

@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred', 'created_at', 'referrer_bonus_given', 'referred_bonus_given', 'bonus_awarded_at')
    list_filter = ('referrer_bonus_given', 'referred_bonus_given', 'created_at', 'bonus_awarded_at')
    search_fields = ('referrer__username', 'referrer__email', 'referred__username', 'referred__email')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('referrer', 'referred', 'referred_first_order')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Referral Information', {
            'fields': ('referrer', 'referred', 'created_at', 'updated_at')
        }),
        ('Bonus Tracking', {
            'fields': ('referrer_bonus_given', 'referred_bonus_given', 'bonus_awarded_at')
        }),
        ('Order Information', {
            'fields': ('referred_first_order',)
        })
    )

@admin.register(UserLoyaltyAccount)
class UserLoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_tier', 'available_points', 'lifetime_earned', 'lifetime_redeemed', 'created_at')
    list_filter = ('current_tier', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-lifetime_earned',)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'current_tier')
        }),
        ('Points Summary', {
            'fields': ('available_points', 'lifetime_earned', 'lifetime_redeemed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('user_account', 'transaction_type', 'points', 'reason', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user_account__user__username', 'user_account__user__email', 'reason')
    readonly_fields = ('created_at', 'balance_after')
    raw_id_fields = ('user_account', 'order')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user_account', 'transaction_type', 'points', 'reason')
        }),
        ('Related Information', {
            'fields': ('order', 'balance_after', 'created_at')
        })
    )

@admin.register(LoyaltyReward)
class LoyaltyRewardAdmin(admin.ModelAdmin):
    list_display = ('title', 'points_required', 'reward_type', 'is_active', 'created_at', 'valid_until')
    list_filter = ('reward_type', 'is_active', 'created_at', 'valid_until')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'current_redemptions')
    
    fieldsets = (
        ('Reward Information', {
            'fields': ('title', 'description', 'points_required', 'reward_type', 'is_active')
        }),
        ('Reward Details', {
            'fields': ('discount_amount', 'discount_percentage', 'max_redemptions_per_user', 'total_redemptions_allowed', 'current_redemptions')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

@admin.register(LoyaltyConfiguration)
class LoyaltyConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'points_per_rupee', 'silver_threshold', 'gold_threshold', 'platinum_threshold', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'is_active')
        }),
        ('Points Earning', {
            'fields': ('points_per_rupee', 'minimum_order_amount')
        }),
        ('Tier Thresholds (Lifetime Points)', {
            'fields': ('bronze_threshold', 'silver_threshold', 'gold_threshold', 'platinum_threshold'),
            'description': 'Points required to reach each tier'
        }),
        ('Tier Multipliers', {
            'fields': ('bronze_multiplier', 'silver_multiplier', 'gold_multiplier', 'platinum_multiplier'),
            'description': 'Points earning multiplier for each tier'
        }),
        ('Bonus Points', {
            'fields': ('referrer_bonus_points', 'referee_bonus_points', 'signup_bonus_points')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(PromotionalBanner)
class PromotionalBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'banner_type', 'offer_code', 'display_location', 'is_active', 'valid_from', 'valid_until', 'current_uses')
    list_filter = ('banner_type', 'display_location', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('title', 'description', 'offer_code')
    readonly_fields = ('created_at', 'updated_at', 'current_uses')
    date_hierarchy = 'valid_from'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'banner_type', 'is_active')
        }),
        ('Visual Design', {
            'fields': ('background_color', 'text_color', 'image'),
            'description': 'Customize the appearance of the banner'
        }),
        ('Offer Details', {
            'fields': ('offer_code', 'discount_amount', 'discount_percentage', 'minimum_order_amount'),
            'description': 'Configure discount and coupon details'
        }),
        ('Display Settings', {
            'fields': ('display_location', 'display_order')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Usage Tracking', {
            'fields': ('max_uses', 'current_uses'),
            'description': 'Track and limit usage of this offer'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for color fields
        form.base_fields['background_color'].help_text = 'Hex color code (e.g., #ff6b35 for orange)'
        form.base_fields['text_color'].help_text = 'Hex color code (e.g., #ffffff for white)'
        return form
