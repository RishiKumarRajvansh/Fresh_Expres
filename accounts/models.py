from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import random
import string

class User(AbstractUser):
    USER_TYPES = [
        ('customer', 'Customer'),
        ('store_owner', 'Store Owner'),
        ('delivery_agent', 'Delivery Agent'),
        ('admin', 'Admin'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Convert email to lowercase before saving
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

class OTPVerification(models.Model):
    OTP_TYPES = [
        ('email', 'Email'),
        ('phone', 'Phone'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    otp_type = models.CharField(max_length=10, choices=OTP_TYPES)
    otp_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        if not self.otp_code:
            self.otp_code = ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @classmethod
    def create_otp(cls, phone_number, otp_type='phone', user=None):
        """Create a new OTP for phone number"""
        # Invalidate any existing OTPs
        cls.objects.filter(phone_number=phone_number, is_verified=False).update(is_verified=True)
        
        # Create new OTP
        otp = cls.objects.create(
            user=user,
            phone_number=phone_number,
            otp_type=otp_type
        )
        return otp
    
    class Meta:
        ordering = ['-created_at']

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], blank=True, null=True)
    
    # Address information
    address_line_1 = models.CharField(max_length=255, blank=True, null=True)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    
    # For delivery agents
    vehicle_type = models.CharField(max_length=50, blank=True, null=True)
    vehicle_number = models.CharField(max_length=20, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Loyalty points for customers
    loyalty_points = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"


class Wishlist(models.Model):
    """User's wishlist for products - Completely rewritten"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    store_product = models.ForeignKey('catalog.StoreProduct', on_delete=models.CASCADE, related_name='wishlist_items')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'store_product')
        ordering = ['-added_at']
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        indexes = [
            models.Index(fields=['user', '-added_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s wishlist - {self.store_product.product.name}"
    
    @property
    def is_available(self):
        """Check if the product is still available"""
        return self.store_product.is_available and self.store_product.availability_status == 'in_stock'


# ============== LOYALTY & REWARDS SYSTEM ==============

class LoyaltyProgram(models.Model):
    """Loyalty program configuration"""
    name = models.CharField(max_length=100)
    points_per_rupee = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    
    # Redemption settings
    min_points_to_redeem = models.PositiveIntegerField(default=100)
    redemption_value_per_point = models.DecimalField(max_digits=5, decimal_places=2, default=0.10)
    
    # Bonus multipliers
    birthday_bonus_multiplier = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    referral_bonus_points = models.PositiveIntegerField(default=100)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class UserLoyaltyAccount(models.Model):
    """User's loyalty account"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_account')
    loyalty_program = models.ForeignKey(LoyaltyProgram, on_delete=models.PROTECT)
    
    total_points = models.PositiveIntegerField(default=0)
    available_points = models.PositiveIntegerField(default=0)
    lifetime_earned = models.PositiveIntegerField(default=0)
    lifetime_redeemed = models.PositiveIntegerField(default=0)
    
    # Tier management
    current_tier = models.CharField(max_length=20, default='Bronze')
    tier_points = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.available_points} points"
    
    def add_points(self, points, reason=""):
        """Add points to user's account"""
        self.total_points += points
        self.available_points += points
        self.lifetime_earned += points
        self.save()
        
        # Create transaction record
        LoyaltyTransaction.objects.create(
            user_account=self,
            transaction_type='earned',
            points=points,
            reason=reason,
            balance_after=self.available_points
        )
        
        # Check for tier upgrade
        self.update_tier()
    
    def redeem_points(self, points, reason=""):
        """Redeem points from user's account"""
        if points > self.available_points:
            raise ValueError("Insufficient points")
        
        self.available_points -= points
        self.lifetime_redeemed += points
        self.save()
        
        # Create transaction record
        LoyaltyTransaction.objects.create(
            user_account=self,
            transaction_type='redeemed',
            points=-points,
            reason=reason,
            balance_after=self.available_points
        )
    
    def update_tier(self):
        """Update user tier based on lifetime points using dynamic configuration"""
        config = LoyaltyConfiguration.get_active_config()
        if not config:
            # Fallback to default values if no configuration exists
            if self.lifetime_earned >= 10000:
                self.current_tier = 'Platinum'
            elif self.lifetime_earned >= 5000:
                self.current_tier = 'Gold'
            elif self.lifetime_earned >= 1000:
                self.current_tier = 'Silver'
            else:
                self.current_tier = 'Bronze'
        else:
            # Use dynamic configuration
            if self.lifetime_earned >= config.platinum_threshold:
                self.current_tier = 'Platinum'
            elif self.lifetime_earned >= config.gold_threshold:
                self.current_tier = 'Gold'
            elif self.lifetime_earned >= config.silver_threshold:
                self.current_tier = 'Silver'
            else:
                self.current_tier = 'Bronze'
        self.save()

    def get_tier_multiplier(self):
        """Get the points multiplier for current tier"""
        config = LoyaltyConfiguration.get_active_config()
        if not config:
            # Default multipliers
            multipliers = {
                'Bronze': 1.0,
                'Silver': 1.2,
                'Gold': 1.5,
                'Platinum': 2.0
            }
            return multipliers.get(self.current_tier, 1.0)
        else:
            multipliers = {
                'Bronze': config.bronze_multiplier,
                'Silver': config.silver_multiplier,
                'Gold': config.gold_multiplier,
                'Platinum': config.platinum_multiplier
            }
            return float(multipliers.get(self.current_tier, 1.0))

    def calculate_points_for_order(self, order_amount):
        """Calculate points to be earned for an order amount"""
        config = LoyaltyConfiguration.get_active_config()
        
        # Check minimum order amount
        if config and order_amount < config.minimum_order_amount:
            return 0
            
        # Base points calculation
        base_points_per_rupee = float(config.points_per_rupee) if config else 1.0
        base_points = int(float(order_amount) * base_points_per_rupee)
        
        # Apply tier multiplier
        multiplier = self.get_tier_multiplier()
        final_points = int(base_points * multiplier)
        
        return final_points

    def get_next_tier_info(self):
        """Get information about next tier progression"""
        config = LoyaltyConfiguration.get_active_config()
        if not config:
            # Default thresholds
            thresholds = {
                'Bronze': 1000,
                'Silver': 5000,
                'Gold': 10000,
                'Platinum': None
            }
        else:
            thresholds = {
                'Bronze': config.silver_threshold,
                'Silver': config.gold_threshold,
                'Gold': config.platinum_threshold,
                'Platinum': None
            }
        
        next_threshold = thresholds.get(self.current_tier)
        if next_threshold is None:
            return None, 0, 100  # Already at highest tier
            
        points_needed = max(0, next_threshold - self.lifetime_earned)
        progress_percent = min(100, (self.lifetime_earned / next_threshold) * 100)
        
        next_tier_names = {
            'Bronze': 'Silver',
            'Silver': 'Gold', 
            'Gold': 'Platinum'
        }
        next_tier = next_tier_names.get(self.current_tier)
        
        return next_tier, points_needed, progress_percent


class LoyaltyTransaction(models.Model):
    """Record of all loyalty point transactions"""
    TRANSACTION_TYPES = [
        ('earned', 'Points Earned'),
        ('redeemed', 'Points Redeemed'),
        ('expired', 'Points Expired'),
        ('bonus', 'Bonus Points'),
        ('referral', 'Referral Bonus'),
    ]
    
    user_account = models.ForeignKey(UserLoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    points = models.IntegerField()  # Can be negative for redemptions
    reason = models.CharField(max_length=200)
    
    # Reference to order if applicable  
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, blank=True, null=True)
    
    balance_after = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user_account.user.username} - {self.transaction_type} - {self.points} points"
    
    class Meta:
        ordering = ['-created_at']


class LoyaltyReward(models.Model):
    """Available loyalty rewards for redemption"""
    REWARD_TYPES = [
        ('discount', 'Discount Coupon'),
        ('free_delivery', 'Free Delivery'),
        ('product', 'Free Product'),
        ('cashback', 'Cashback'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    reward_type = models.CharField(max_length=15, choices=REWARD_TYPES)
    
    # Points required
    points_required = models.PositiveIntegerField()
    
    # Reward value
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Availability
    is_active = models.BooleanField(default=True)
    max_redemptions_per_user = models.PositiveIntegerField(default=1)
    total_redemptions_allowed = models.PositiveIntegerField(blank=True, null=True)
    current_redemptions = models.PositiveIntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title


class UserRewardRedemption(models.Model):
    """Track user reward redemptions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reward = models.ForeignKey(LoyaltyReward, on_delete=models.CASCADE)
    points_used = models.PositiveIntegerField()
    
    # Coupon details
    coupon_code = models.CharField(max_length=20, unique=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True)
    
    # Order reference when used
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"{self.user.username} - {self.reward.title}"
    
    def save(self, *args, **kwargs):
        if not self.coupon_code:
            self.coupon_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        super().save(*args, **kwargs)


class LoyaltyConfiguration(models.Model):
    """Dynamic loyalty program configuration"""
    name = models.CharField(max_length=100, default="Default Loyalty Program")
    
    # Points earning configuration
    points_per_rupee = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, 
                                         help_text="Points earned per rupee spent")
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                             help_text="Minimum order amount to earn points")
    
    # Tier configuration  
    bronze_threshold = models.PositiveIntegerField(default=0)
    silver_threshold = models.PositiveIntegerField(default=1000)
    gold_threshold = models.PositiveIntegerField(default=2000) 
    platinum_threshold = models.PositiveIntegerField(default=3000)
    
    # Tier multipliers
    bronze_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    silver_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.2)
    gold_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.5)
    platinum_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=2.0)
    
    # Referral bonuses
    referrer_bonus_points = models.PositiveIntegerField(default=100)
    referee_bonus_points = models.PositiveIntegerField(default=50)
    signup_bonus_points = models.PositiveIntegerField(default=25)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"
    
    def save(self, *args, **kwargs):
        # Ensure only one active configuration
        if self.is_active:
            LoyaltyConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_config(cls):
        """Get the currently active loyalty configuration"""
        return cls.objects.filter(is_active=True).first()


class PromotionalBanner(models.Model):
    """Dynamic promotional banners and offers"""
    BANNER_TYPES = [
        ('offer', 'Special Offer'),
        ('festival', 'Festival Promotion'),
        ('announcement', 'General Announcement'),
        ('coupon', 'Coupon Code'),
    ]
    
    DISPLAY_LOCATIONS = [
        ('home_top', 'Home Page Top'),
        ('home_middle', 'Home Page Middle'),
        ('home_bottom', 'Home Page Bottom'),
        ('loyalty_dashboard', 'Loyalty Dashboard'),
        ('checkout', 'Checkout Page'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    banner_type = models.CharField(max_length=20, choices=BANNER_TYPES, default='offer')
    
    # Visual elements
    background_color = models.CharField(max_length=7, default='#ff6b35', 
                                      help_text="Hex color code (e.g., #ff6b35)")
    text_color = models.CharField(max_length=7, default='#ffffff',
                                help_text="Hex color code (e.g., #ffffff)")
    image = models.ImageField(upload_to='banners/', blank=True, null=True)
    
    # Offer details
    offer_code = models.CharField(max_length=20, blank=True, 
                                help_text="Coupon code users can use")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Display settings
    display_location = models.CharField(max_length=20, choices=DISPLAY_LOCATIONS, default='home_top')
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True)
    
    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    
    # Usage tracking
    max_uses = models.PositiveIntegerField(blank=True, null=True, 
                                         help_text="Maximum number of times this offer can be used")
    current_uses = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_banner_type_display()})"
    
    def is_valid(self):
        """Check if banner is currently valid"""
        now = timezone.now()
        return (self.is_active and 
                self.valid_from <= now <= self.valid_until and
                (self.max_uses is None or self.current_uses < self.max_uses))
    
    def can_use_offer(self):
        """Check if offer can still be used"""
        return self.is_valid() and self.offer_code
    
    @classmethod 
    def get_active_banners(cls, location=None):
        """Get active banners for a specific location"""
        now = timezone.now()
        queryset = cls.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).order_by('display_order', '-created_at')
        
        if location:
            queryset = queryset.filter(display_location=location)
            
        return queryset


class ReferralProgram(models.Model):
    """Referral program management"""
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_by_user')
    
    # Bonus tracking
    referrer_bonus_given = models.BooleanField(default=False)
    referred_bonus_given = models.BooleanField(default=False)
    
    # First order tracking
    referred_first_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, blank=True, null=True)
    bonus_awarded_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.referrer.username} referred {self.referred.username}"
