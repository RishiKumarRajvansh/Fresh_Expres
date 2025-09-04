from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import TimeStampedModel
from stores.models import Store
import uuid

User = get_user_model()

class Category(TimeStampedModel):
    """Product categories (admin-only creation)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='subcategories')
    
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name
    
    @property
    def full_path(self):
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name
    
    @property
    def is_subcategory(self):
        return self.parent is not None
    
    @property 
    def main_category(self):
        if self.parent:
            return self.parent.main_category
        return self
    
    def clean(self):
        # Prevent circular references
        if self.parent:
            if self.parent == self:
                raise ValidationError("Category cannot be its own parent.")
            if self.parent.parent and self.parent.parent == self:
                raise ValidationError("Circular reference detected.")
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = "Categories"

class Product(TimeStampedModel):
    """Global product catalog"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    # Product attributes
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    
    # Physical attributes
    weight_per_unit = models.DecimalField(max_digits=6, decimal_places=2, help_text="Weight in grams")
    unit_type = models.CharField(max_length=20, default='grams')
    
    # Images (1 main image is required, up to 4 additional images)
    image = models.ImageField(upload_to='products/', blank=True, null=True, help_text="Main product image (required)")
    
    def generate_sku(self):
        """Generate a unique SKU for the product"""
        import re
        from django.utils.text import slugify
        
        # Get category abbreviation (first 3 letters, uppercase)
        category_abbr = re.sub(r'[^a-zA-Z]', '', self.category.name)[:3].upper()
        if len(category_abbr) < 2:
            category_abbr = "PRD"  # Default fallback
        
        # Get product name abbreviation (first 3 letters, uppercase)
        product_abbr = re.sub(r'[^a-zA-Z]', '', self.name)[:3].upper()
        if len(product_abbr) < 2:
            product_abbr = "ITM"  # Default fallback
        
        # Generate base SKU
        base_sku = f"{category_abbr}{product_abbr}"
        
        # Find highest existing number for this base
        import re
        existing_skus = Product.objects.filter(
            sku__startswith=base_sku
        ).values_list('sku', flat=True)
        
        max_num = 0
        for sku in existing_skus:
            match = re.search(rf'{base_sku}(\d+)$', sku)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        
        # Generate new SKU with next number
        new_sku = f"{base_sku}{max_num + 1:03d}"
        return new_sku
    
    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            self.sku = self.generate_sku()
        super().save(*args, **kwargs)
    
    def clean(self):
        # Ensure main image is provided
        if not self.image:
            raise ValidationError("Main product image is required.")
    
    @property
    def all_images(self):
        """Get all images including main image and additional images"""
        images = [self.image] if self.image else []
        images.extend([img.image for img in self.images.filter(is_active=True).order_by('sort_order')])
        return images
    
    @property
    def additional_images_count(self):
        return self.images.filter(is_active=True).count()
    
    def can_add_image(self):
        """Check if more images can be added (max 5 total: 1 main + 4 additional)"""
        return self.additional_images_count < 4
    
    # Nutritional info (optional)
    nutritional_info = models.JSONField(default=dict, blank=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['slug']),
        ]

class ProductImage(TimeStampedModel):
    """Additional product images (max 4 per product)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def clean(self):
        # Check image limit (4 additional images max)
        if self.product and self.product.additional_images_count >= 4 and not self.pk:
            raise ValidationError("Maximum 4 additional images allowed per product (5 total including main image).")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['sort_order']

class StoreProduct(TimeStampedModel):
    """Store-specific product information"""
    AVAILABILITY_STATUS = [
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('pre_order', 'Pre-order'),
        ('discontinued', 'Discontinued'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='store_products')
    
    # Pricing
    price = models.DecimalField(max_digits=8, decimal_places=2)
    compare_price = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    
    # Inventory
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_STATUS, default='in_stock')
    
    # Store-specific settings
    is_featured = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    
    # Custom fields for this store
    store_notes = models.TextField(blank=True, null=True)
    prep_time_minutes = models.PositiveIntegerField(default=0, help_text="Additional prep time")
    
    def __str__(self):
        return f"{self.store.name} - {self.product.name}"
    
    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold
    
    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return round(((self.compare_price - self.price) / self.compare_price) * 100, 2)
        return 0
    
    class Meta:
        unique_together = ['store', 'product']
        ordering = ['-is_featured', 'product__name']
        indexes = [
            models.Index(fields=['store', 'availability_status', 'is_available']),
            models.Index(fields=['is_featured', 'is_available']),
        ]

class Ingredient(TimeStampedModel):
    """Ingredients for products"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='ingredients/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class ProductIngredient(TimeStampedModel):
    """Ingredients associated with products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.CharField(max_length=50, blank=True, null=True)
    is_optional = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.product.name} - {self.ingredient.name}"
    
    class Meta:
        unique_together = ['product', 'ingredient']

class StoreIngredient(TimeStampedModel):
    """Store-specific ingredient pricing and availability"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    is_available = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.store.name} - {self.ingredient.name}"
    
    class Meta:
        unique_together = ['store', 'ingredient']

class ProductSuggestion(TimeStampedModel):
    """Product suggestions (frequently bought together, etc.)"""
    SUGGESTION_TYPES = [
        ('frequently_bought', 'Frequently Bought Together'),
        ('complete_dish', 'Complete the Dish'),
        ('similar', 'Similar Products'),
        ('upsell', 'Upsell'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='suggestions')
    suggested_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='suggested_for')
    suggestion_type = models.CharField(max_length=20, choices=SUGGESTION_TYPES, default='frequently_bought')
    
    # Weighting for ordering suggestions
    weight = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.product.name} -> {self.suggested_product.name} ({self.get_suggestion_type_display()})"
    
    class Meta:
        unique_together = ['product', 'suggested_product', 'suggestion_type']
        ordering = ['-weight', 'suggested_product__name']

class ProductReview(TimeStampedModel):
    """Product reviews by customers"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='product_reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=200, blank=True, null=True)
    review_text = models.TextField(blank=True, null=True)
    
    # Review metadata
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.rating}/5 by {self.user.username}"
    
    class Meta:
        unique_together = ['product', 'store', 'user']
        ordering = ['-created_at']
