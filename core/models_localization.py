"""
Cultural Localization and Regional Features for Hyperlocal Platform
Handles regional preferences, cultural dietary requirements, and local festivals
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import JSONField
from core.models import TimeStampedModel

User = get_user_model()


class Region(TimeStampedModel):
    """Geographical regions with cultural context"""
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50, default='India')
    
    # Geographic boundaries
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    radius_km = models.PositiveIntegerField(default=50, help_text="Service radius in kilometers")
    
    # Cultural information
    primary_language = models.CharField(max_length=10, default='en')
    secondary_languages = JSONField(default=list, help_text="List of language codes")
    
    # Regional preferences
    currency = models.CharField(max_length=3, default='INR')
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    
    # Dietary culture
    vegetarian_preference = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        help_text="Percentage of vegetarian population"
    )
    
    # Cultural metadata
    cultural_notes = models.TextField(blank=True)
    dietary_restrictions = JSONField(default=list, help_text="Common dietary restrictions in this region")
    festival_calendar = JSONField(default=dict, help_text="Regional festivals and their dates")
    
    # Business settings
    peak_hours = JSONField(default=dict, help_text="Peak business hours by day")
    delivery_preferences = JSONField(default=dict, help_text="Regional delivery preferences")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['state', 'is_active']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.state}"
    
    def get_supported_languages(self):
        """Get all supported languages for this region"""
        languages = [self.primary_language]
        languages.extend(self.secondary_languages)
        return list(set(languages))  # Remove duplicates


class CulturalPreference(TimeStampedModel):
    """User's cultural and dietary preferences"""
    DIETARY_TYPES = [
        ('omnivore', 'Omnivore'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('pescatarian', 'Pescatarian'),
        ('flexitarian', 'Flexitarian'),
        ('keto', 'Ketogenic'),
        ('paleo', 'Paleo'),
        ('gluten_free', 'Gluten Free'),
    ]
    
    RELIGIOUS_PREFERENCES = [
        ('none', 'No Preference'),
        ('hindu', 'Hindu'),
        ('muslim', 'Muslim'),
        ('christian', 'Christian'),
        ('sikh', 'Sikh'),
        ('buddhist', 'Buddhist'),
        ('jain', 'Jain'),
        ('jewish', 'Jewish'),
        ('other', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cultural_preference')
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Language preferences
    preferred_language = models.CharField(max_length=10, default='en')
    secondary_language = models.CharField(max_length=10, blank=True)
    
    # Dietary preferences
    dietary_type = models.CharField(max_length=20, choices=DIETARY_TYPES, default='omnivore')
    religious_preference = models.CharField(max_length=15, choices=RELIGIOUS_PREFERENCES, default='none')
    
    # Specific restrictions
    avoid_ingredients = JSONField(default=list, help_text="List of ingredients to avoid")
    allergies = JSONField(default=list, help_text="List of food allergies")
    
    # Cultural preferences
    prefers_halal = models.BooleanField(default=False)
    prefers_kosher = models.BooleanField(default=False)
    prefers_jain_food = models.BooleanField(default=False)
    avoid_beef = models.BooleanField(default=False)
    avoid_pork = models.BooleanField(default=False)
    
    # Spice and taste preferences
    spice_tolerance = models.CharField(
        max_length=10,
        choices=[('mild', 'Mild'), ('medium', 'Medium'), ('hot', 'Hot'), ('extra_hot', 'Extra Hot')],
        default='medium'
    )
    
    taste_preferences = JSONField(default=dict, help_text="Preferences for sweet, salty, sour, etc.")
    
    # Regional cuisine preferences
    favorite_cuisines = JSONField(default=list, help_text="List of preferred cuisines")
    regional_specialties = JSONField(default=list, help_text="Preferred regional dishes")
    
    # Shopping preferences
    prefers_local_brands = models.BooleanField(default=True)
    organic_preference = models.BooleanField(default=False)
    premium_preference = models.BooleanField(default=False)
    
    # Festival and seasonal preferences
    follows_fasting_calendar = models.BooleanField(default=False)
    fasting_preferences = JSONField(default=dict, help_text="Fasting preferences and dates")
    
    def __str__(self):
        return f"{self.user.username} - Cultural Preferences"
    
    def get_dietary_restrictions(self):
        """Get comprehensive list of dietary restrictions"""
        restrictions = []
        
        # Based on dietary type
        if self.dietary_type == 'vegetarian':
            restrictions.extend(['meat', 'poultry', 'fish', 'seafood'])
        elif self.dietary_type == 'vegan':
            restrictions.extend(['meat', 'poultry', 'fish', 'seafood', 'dairy', 'eggs', 'honey'])
        elif self.dietary_type == 'pescatarian':
            restrictions.extend(['meat', 'poultry'])
        
        # Religious restrictions
        if self.religious_preference == 'hindu' or self.avoid_beef:
            restrictions.append('beef')
        
        if self.religious_preference == 'muslim' or self.prefers_halal:
            restrictions.extend(['pork', 'non_halal_meat'])
        
        if self.religious_preference == 'jewish' or self.prefers_kosher:
            restrictions.extend(['pork', 'non_kosher_meat', 'shellfish'])
        
        if self.avoid_pork:
            restrictions.append('pork')
        
        if self.religious_preference == 'jain' or self.prefers_jain_food:
            restrictions.extend(['meat', 'poultry', 'fish', 'seafood', 'eggs', 'root_vegetables'])
        
        # Add specific ingredients and allergies
        restrictions.extend(self.avoid_ingredients)
        restrictions.extend(self.allergies)
        
        return list(set(restrictions))  # Remove duplicates
    
    def is_compatible_product(self, product):
        """Check if a product is compatible with user's preferences"""
        restrictions = self.get_dietary_restrictions()
        product_tags = getattr(product, 'dietary_tags', [])
        product_ingredients = getattr(product, 'ingredients', [])
        
        # Check if product contains restricted items
        for restriction in restrictions:
            if restriction in product_tags or restriction in product_ingredients:
                return False
        
        return True


class LocalFestival(TimeStampedModel):
    """Regional festivals and their impact on business"""
    FESTIVAL_TYPES = [
        ('religious', 'Religious Festival'),
        ('cultural', 'Cultural Festival'),
        ('harvest', 'Harvest Festival'),
        ('seasonal', 'Seasonal Festival'),
        ('national', 'National Holiday'),
        ('regional', 'Regional Celebration'),
    ]
    
    name = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    festival_type = models.CharField(max_length=15, choices=FESTIVAL_TYPES)
    
    # Timing information
    start_date = models.DateField()
    end_date = models.DateField()
    is_annual = models.BooleanField(default=True)
    duration_days = models.PositiveIntegerField(default=1)
    
    # Business impact
    expected_demand_increase = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Percentage increase in demand"
    )
    
    # Festival-specific products
    special_products = models.ManyToManyField(
        'catalog.Product', 
        blank=True, 
        related_name='associated_festivals',
        help_text="Products specifically associated with this festival"
    )
    
    # Cultural information
    description = models.TextField()
    traditional_foods = JSONField(default=list, help_text="Traditional foods associated with festival")
    customs = JSONField(default=list, help_text="Festival customs and traditions")
    
    # Business settings
    special_offers_enabled = models.BooleanField(default=True)
    extended_delivery_hours = models.BooleanField(default=False)
    priority_delivery = models.BooleanField(default=True)
    
    # Marketing
    marketing_messages = JSONField(default=dict, help_text="Festival-specific marketing messages by language")
    promotional_banners = JSONField(default=list, help_text="Banner URLs for festival promotion")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['start_date', 'name']
        indexes = [
            models.Index(fields=['region', 'start_date']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.region.name}"
    
    def is_ongoing(self, date=None):
        """Check if festival is currently ongoing"""
        if date is None:
            date = timezone.now().date()
        
        return self.start_date <= date <= self.end_date
    
    def is_upcoming(self, days=7):
        """Check if festival is upcoming within specified days"""
        current_date = timezone.now().date()
        return 0 <= (self.start_date - current_date).days <= days


class RegionalProduct(TimeStampedModel):
    """Products specific to regions with cultural context"""
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    
    # Regional naming
    local_name = models.CharField(max_length=200, help_text="Local name in regional language")
    local_name_translation = models.CharField(max_length=200, blank=True)
    
    # Cultural significance
    cultural_significance = models.TextField(blank=True)
    traditional_uses = JSONField(default=list, help_text="Traditional uses and preparation methods")
    
    # Regional pricing
    regional_price_modifier = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=1.00,
        help_text="Price multiplier for this region"
    )
    
    # Seasonal availability
    peak_season_start = models.CharField(max_length=20, blank=True, help_text="Peak season start month")
    peak_season_end = models.CharField(max_length=20, blank=True, help_text="Peak season end month")
    
    # Local sourcing
    local_suppliers = models.ManyToManyField(
        'stores.Store', 
        blank=True,
        related_name='regional_products',
        help_text="Local stores that supply this product"
    )
    
    # Marketing content
    regional_description = models.TextField(blank=True, help_text="Region-specific product description")
    regional_images = JSONField(default=list, help_text="Region-specific product images")
    
    # Availability settings
    is_available = models.BooleanField(default=True)
    minimum_order_quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['product', 'region']
    
    def __str__(self):
        return f"{self.product.name} in {self.region.name}"
    
    def get_regional_price(self, base_price):
        """Calculate regional price based on modifier"""
        return base_price * self.regional_price_modifier


class LocalizationContent(TimeStampedModel):
    """Localized content for different languages and regions"""
    CONTENT_TYPES = [
        ('category_name', 'Category Name'),
        ('product_description', 'Product Description'),
        ('ui_text', 'UI Text'),
        ('marketing_message', 'Marketing Message'),
        ('notification_template', 'Notification Template'),
        ('email_template', 'Email Template'),
        ('sms_template', 'SMS Template'),
    ]
    
    content_type = models.CharField(max_length=25, choices=CONTENT_TYPES)
    content_key = models.CharField(max_length=200, help_text="Unique identifier for the content")
    language_code = models.CharField(max_length=10, default='en')
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True)
    
    # Content
    translated_content = models.TextField()
    context_notes = models.TextField(blank=True, help_text="Context for translators")
    
    # Quality control
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    parent_content = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ['content_key', 'language_code', 'region']
        indexes = [
            models.Index(fields=['content_type', 'language_code']),
            models.Index(fields=['region', 'language_code']),
        ]
    
    def __str__(self):
        region_name = self.region.name if self.region else 'Global'
        return f"{self.content_key} ({self.language_code}) - {region_name}"


class WeatherSeasonality(TimeStampedModel):
    """Weather-based product recommendations and seasonal adjustments"""
    WEATHER_CONDITIONS = [
        ('sunny', 'Sunny'),
        ('rainy', 'Rainy'),
        ('cloudy', 'Cloudy'),
        ('windy', 'Windy'),
        ('cold', 'Cold'),
        ('hot', 'Hot'),
        ('humid', 'Humid'),
        ('dry', 'Dry'),
    ]
    
    SEASONS = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('monsoon', 'Monsoon'),
        ('autumn', 'Autumn'),
        ('winter', 'Winter'),
    ]
    
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    season = models.CharField(max_length=15, choices=SEASONS)
    weather_condition = models.CharField(max_length=15, choices=WEATHER_CONDITIONS)
    
    # Product recommendations
    recommended_products = models.ManyToManyField(
        'catalog.Product',
        blank=True,
        related_name='weather_recommendations',
        help_text="Products recommended for this weather/season"
    )
    
    # Business adjustments
    demand_multiplier = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        default=1.00,
        help_text="Demand adjustment multiplier"
    )
    
    price_adjustment = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Price adjustment percentage"
    )
    
    # Messaging
    marketing_message = models.TextField(blank=True)
    customer_tips = models.TextField(blank=True, help_text="Tips for customers during this weather")
    
    # Validity period
    start_month = models.PositiveIntegerField(help_text="Start month (1-12)")
    end_month = models.PositiveIntegerField(help_text="End month (1-12)")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['region', 'season', 'weather_condition']
    
    def __str__(self):
        return f"{self.season.title()} {self.weather_condition} in {self.region.name}"
    
    def is_current_season(self):
        """Check if this is the current season"""
        current_month = timezone.now().month
        
        if self.start_month <= self.end_month:
            return self.start_month <= current_month <= self.end_month
        else:
            # Season spans across year boundary
            return current_month >= self.start_month or current_month <= self.end_month


class CulturalInsight(TimeStampedModel):
    """Cultural insights and analytics for business intelligence"""
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    insight_date = models.DateField()
    
    # Cultural data
    vegetarian_orders_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    religious_preference_breakdown = JSONField(default=dict)
    popular_cuisines = JSONField(default=list)
    festival_impact_data = JSONField(default=dict)
    
    # Language usage
    language_preference_breakdown = JSONField(default=dict)
    primary_language_usage = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    
    # Seasonal patterns
    seasonal_product_preferences = JSONField(default=dict)
    weather_impact_data = JSONField(default=dict)
    
    # Business metrics
    cultural_preference_accuracy = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Accuracy of cultural preference predictions"
    )
    
    regional_customer_satisfaction = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Regional customer satisfaction score"
    )
    
    class Meta:
        unique_together = ['region', 'insight_date']
        ordering = ['-insight_date', 'region']
    
    def __str__(self):
        return f"Cultural Insights - {self.region.name} ({self.insight_date})"
