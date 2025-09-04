from django.contrib import admin
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from .models import (
    Category, Product, ProductImage, StoreProduct, 
    Ingredient, StoreIngredient, ProductIngredient,
    ProductSuggestion, ProductReview
)

def is_admin_or_superuser(user):
    """Check if user is admin or superuser"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin-only Category management"""
    list_display = ('name', 'parent', 'full_path', 'is_active', 'sort_order', 'created_at')
    list_filter = ('is_active', 'parent', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'sort_order')
    ordering = ('sort_order', 'name')
    
    def get_queryset(self, request):
        """Only show categories to admin users"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.none()
    
    def has_module_permission(self, request):
        """Only allow admin access to category module"""
        return is_admin_or_superuser(request.user)
    
    def has_view_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def has_add_permission(self, request):
        return is_admin_or_superuser(request.user)
    
    def has_change_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def has_delete_permission(self, request, obj=None):
        return is_admin_or_superuser(request.user)
    
    def full_path(self, obj):
        """Display full category path"""
        return obj.full_path
    full_path.short_description = 'Category Path'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent')
        }),
        ('Content', {
            'fields': ('description', 'image')
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order')
        })
    )

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 4  # Maximum 4 additional images
    fields = ('image', 'alt_text', 'sort_order', 'is_active')
    readonly_fields = ()
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        class CustomFormSet(formset):
            def clean(self):
                if any(self.errors):
                    return
                active_images = 0
                for form in self.forms:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                        if form.cleaned_data.get('is_active', True):
                            active_images += 1
                
                if active_images > 4:
                    raise ValidationError("Maximum 4 additional images allowed per product.")
        
        return CustomFormSet

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'sku', 'unit_type', 'image_count', 'is_active', 'created_at')
    list_filter = ('category', 'unit_type', 'is_active', 'created_at')
    search_fields = ('name', 'sku', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    
    def image_count(self, obj):
        """Show total image count (main + additional)"""
        additional_count = obj.additional_images_count
        main_image = 1 if obj.image else 0
        return f"{main_image + additional_count}/5"
    image_count.short_description = 'Images'
    
    def save_model(self, request, obj, form, change):
        """Override save to ensure admin-created products are assigned to a store"""
        super().save_model(request, obj, form, change)
        
        if not change:  # Only for new products
            from stores.models import Store
            
            # Try to find admin's own store first
            admin_store = None
            if hasattr(request.user, 'owned_stores'):
                admin_store = request.user.owned_stores.filter(is_active=True).first()
            
            # If admin doesn't have a store, create one
            if not admin_store:
                admin_store, created = Store.objects.get_or_create(
                    owner=request.user,
                    defaults={
                        'name': 'Admin Store',
                        'store_code': f'ADMIN{request.user.id:04d}',
                        'phone_number': '9999999999',
                        'email': request.user.email,
                        'address_line_1': 'Admin Address',
                        'city': 'Delhi',
                        'state': 'Delhi',
                        'zip_code': '110001',
                        'status': 'open',
                        'is_active': True
                    }
                )
            
            # Create StoreProduct entry
            StoreProduct.objects.get_or_create(
                store=admin_store,
                product=obj,
                defaults={
                    'price': 0.00,  # Admin should set price later
                    'stock_quantity': 0,  # Admin should set stock later
                    'is_available': False,  # Admin should make it available after setting price/stock
                }
            )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description')
        }),
        ('Product Details', {
            'fields': ('sku', 'brand', 'weight_per_unit', 'unit_type')
        }),
        ('Main Image', {
            'fields': ('image',),
            'description': 'Main product image (required). Additional images can be added below.'
        }),
        ('Additional Information', {
            'fields': ('nutritional_info',),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active',)
        })
    )

@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'store', 'price', 'stock_quantity', 'is_available', 'updated_at')
    list_filter = ('is_available', 'store', 'updated_at')
    search_fields = ('product__name', 'store__name')

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')

@admin.register(ProductSuggestion)
class ProductSuggestionAdmin(admin.ModelAdmin):
    list_display = ('product', 'suggested_product', 'suggestion_type', 'weight', 'is_active')
    list_filter = ('suggestion_type', 'is_active', 'created_at')
    search_fields = ('product__name', 'suggested_product__name')

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_verified_purchase', 'created_at')
    list_filter = ('rating', 'is_verified_purchase', 'created_at')
    search_fields = ('product__name', 'user__username', 'review_text')
