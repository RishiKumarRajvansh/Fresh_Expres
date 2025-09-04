from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.http import JsonResponse
from django.db.models import Q, Count, Min, Max
from django.core.paginator import Paginator
from stores.models import Store
from locations.models import ZipArea
from .models import Category, Product, StoreProduct, ProductReview
from stores.models import Store
from locations.models import ZipArea
from .models import Category, Product, StoreProduct, ProductReview

class ProductListView(ListView):
    """Enhanced product listing with advanced filtering"""
    template_name = 'catalog/product_list_enhanced.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure ZIP code is selected
        if not request.session.get('selected_zip_code'):
            return redirect('core:zip_capture')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Get selected ZIP code from session
        selected_zip = self.request.session.get('selected_zip_code')
        
        if not selected_zip:
            return StoreProduct.objects.none()
        
        # Get all stores that serve the selected ZIP area through StoreZipCoverage
        try:
            from locations.models import ZipArea
            from stores.models import StoreZipCoverage
            
            zip_area = ZipArea.objects.get(zip_code=selected_zip, is_active=True)
            available_stores = Store.objects.filter(
                zip_coverages__zip_area=zip_area,
                zip_coverages__is_active=True,
                is_active=True,
                status='open'
            ).distinct()
        except ZipArea.DoesNotExist:
            return StoreProduct.objects.none()
        
        # Get products from all stores in the area
        queryset = StoreProduct.objects.filter(
            store__in=available_stores,
            is_available=True,
            availability_status='in_stock'
        ).select_related('product', 'store', 'product__category').order_by('product__name')
        
        # Apply category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(product__category__slug=category_slug)
        
        # Apply subcategory filter
        subcategory_slug = self.request.GET.get('subcategory')
        if subcategory_slug:
            queryset = queryset.filter(product__category__slug=subcategory_slug)
        
        # Apply search filter
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(product__description__icontains=search_query) |
                Q(product__category__name__icontains=search_query)
            )
        
        # Apply price range filter
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
        
        # Apply unit type filter
        unit_type = self.request.GET.get('unit_type')
        if unit_type:
            queryset = queryset.filter(product__unit_type=unit_type)
        
        # Apply sorting
        sort_by = self.request.GET.get('sort', 'name')
        if sort_by == 'price_low':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_high':
            queryset = queryset.order_by('-price')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'popular':
            # Sort by availability and stock quantity
            queryset = queryset.order_by('-stock_quantity')
        else:  # Default to name
            queryset = queryset.order_by('product__name')
        
        # Apply availability filter
        only_available = self.request.GET.get('available')
        if only_available == '1':
            queryset = queryset.filter(stock_quantity__gt=0)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get ZIP information
        selected_zip = self.request.session.get('selected_zip_code')
        if selected_zip:
            try:
                from locations.models import ZipArea
                from stores.models import StoreZipCoverage
                
                zip_area = ZipArea.objects.get(zip_code=selected_zip, is_active=True)
                context['selected_zip'] = selected_zip
                context['zip_area'] = zip_area
                
                # Get all stores that serve this ZIP area
                available_stores = Store.objects.filter(
                    zip_coverages__zip_area=zip_area,
                    zip_coverages__is_active=True,
                    is_active=True,
                    status='open'
                ).distinct()
                context['available_stores'] = available_stores
                context['store_count'] = available_stores.count()
            except ZipArea.DoesNotExist:
                pass
        
        # Get categories for filtering (only active categories with products from stores in the area)
        if selected_zip:
            try:
                from locations.models import ZipArea
                from stores.models import StoreZipCoverage
                
                zip_area = ZipArea.objects.get(zip_code=selected_zip, is_active=True)
                available_stores = Store.objects.filter(
                    zip_coverages__zip_area=zip_area,
                    zip_coverages__is_active=True,
                    is_active=True,
                    status='open'
                ).distinct()
                
                categories = Category.objects.filter(
                    is_active=True,
                    parent__isnull=True,
                    product__storeproduct__store__in=available_stores,
                    product__storeproduct__is_available=True
                ).distinct().order_by('sort_order', 'name')
                context['categories'] = categories
            except ZipArea.DoesNotExist:
                context['categories'] = Category.objects.none()
        else:
            context['categories'] = Category.objects.none()
        
        # Get subcategories if category is selected
        category_slug = self.request.GET.get('category')
        if category_slug and selected_zip:
            try:
                selected_category = Category.objects.get(slug=category_slug)
                context['selected_category'] = selected_category
                available_stores = Store.objects.filter(
                    zip_code=selected_zip,
                    is_active=True,
                    status='open'
                )
                subcategories = Category.objects.filter(
                    parent=selected_category,
                    is_active=True,
                    product__storeproduct__store__in=available_stores,
                    product__storeproduct__is_available=True
                ).distinct().order_by('sort_order', 'name')
                context['subcategories'] = subcategories
            except Category.DoesNotExist:
                pass
        
        # Get price range for filtering
        if selected_zip:
            available_stores = Store.objects.filter(
                zip_code=selected_zip,
                is_active=True,
                status='open'
            )
            price_range = StoreProduct.objects.filter(
                store__in=available_stores,
                is_available=True
            ).aggregate(
                min_price=Min('price'),
                max_price=Max('price')
            )
            context['price_range'] = price_range
        
        # Get unit types for filtering
        if selected_zip:
            available_stores = Store.objects.filter(
                zip_code=selected_zip,
                is_active=True,
                status='open'
            )
            unit_types = StoreProduct.objects.filter(
                store__in=available_stores,
                is_available=True
            ).values_list('product__unit_type', flat=True).distinct()
            context['unit_types'] = [ut for ut in unit_types if ut]
        
        # Current filters for display
        context['current_filters'] = {
            'category': self.request.GET.get('category', ''),
            'subcategory': self.request.GET.get('subcategory', ''),
            'q': self.request.GET.get('q', ''),
            'min_price': self.request.GET.get('min_price', ''),
            'max_price': self.request.GET.get('max_price', ''),
            'unit_type': self.request.GET.get('unit_type', ''),
            'sort': self.request.GET.get('sort', 'name'),
            'available': self.request.GET.get('available', ''),
        }
        
        return context
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get store and ZIP info
        store_id = self.request.session.get('selected_store_id')
        selected_zip = self.request.session.get('selected_zip_code')
        
        if store_id and selected_zip:
            try:
                store = Store.objects.get(id=store_id)
                zip_area = ZipArea.objects.get(zip_code=selected_zip)
                
                context['selected_store'] = store
                context['zip_area'] = zip_area
                
                # Get categories with product counts for the selected store
                context['categories'] = Category.objects.filter(
                    products__store_products__store=store,
                    products__store_products__is_available=True,
                    is_active=True
                ).annotate(
                    product_count=Count('products__store_products', filter=Q(
                        products__store_products__store=store,
                        products__store_products__is_available=True
                    ))
                ).distinct().order_by('name')
                
            except (Store.DoesNotExist, ZipArea.DoesNotExist):
                pass
        
        return context

class CategoryProductsView(ProductListView):
    """Show products from a specific category for the selected store"""
    template_name = 'catalog/category_products.html'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        category_slug = self.kwargs.get('category_slug')
        
        if category_slug:
            queryset = queryset.filter(product__category__slug=category_slug)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get('category_slug')
        
        if category_slug:
            try:
                context['category'] = Category.objects.get(slug=category_slug, is_active=True)
            except Category.DoesNotExist:
                pass
        
        return context

class CategoryDetailView(DetailView):
    """Show category detail page"""
    model = Category
    template_name = 'catalog/category_detail.html'
    context_object_name = 'category'
    pk_url_kwarg = 'category_id'
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()
        
        # Get products in this category from the selected store
        store_id = self.request.session.get('selected_store_id')
        if store_id:
            try:
                store = Store.objects.get(id=store_id, is_active=True)
                context['products'] = StoreProduct.objects.filter(
                    store=store,
                    product__category=category,
                    is_available=True,
                    availability_status='in_stock'
                ).select_related('product', 'store')[:20]
            except Store.DoesNotExist:
                context['products'] = StoreProduct.objects.none()
        else:
            context['products'] = StoreProduct.objects.none()
            
        return context

class ProductSearchView(ProductListView):
    """Search products within the selected store"""
    template_name = 'catalog/product_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context

class ProductDetailView(DetailView):
    """Show detailed view of a product from the selected store"""
    template_name = 'catalog/product_detail.html'
    context_object_name = 'store_product'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('selected_zip_code'):
            return redirect('core:zip_capture')
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        selected_zip = self.request.session.get('selected_zip_code')
        product_slug = self.kwargs.get('product_slug')
        
        if not selected_zip or not product_slug:
            return None
        
        # Get stores in the selected zip area
        available_stores = Store.objects.filter(
            zip_code=selected_zip,
            is_active=True,
            status='open'
        )
        
        # Get the product from any available store (preferably the cheapest)
        return StoreProduct.objects.filter(
            store__in=available_stores,
            product__slug=product_slug,
            is_available=True
        ).select_related('product', 'store').order_by('price').first()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store_product = self.get_object()

        # If we found a StoreProduct (product available in selected area), expose detailed context
        if store_product:
            # Provide both the Product and StoreProduct objects to the template
            context['store_product'] = store_product
            context['product'] = store_product.product

            selected_zip = self.request.session.get('selected_zip_code')
            stores_in_area = Store.objects.filter(
                zip_code=selected_zip,
                is_active=True,
                status='open'
            )

            # Get all available StoreProduct options for this product from different stores
            available_store_products = StoreProduct.objects.filter(
                store__in=stores_in_area,
                product=store_product.product,
                is_available=True
            ).select_related('store').order_by('price')

            context['available_stores'] = available_store_products
            context['product_options'] = available_store_products

            # Derive availability from store-specific data (prefer store_product first)
            try:
                context['is_available'] = bool(
                    store_product.availability_status == 'in_stock' and store_product.stock_quantity > 0
                )
            except Exception:
                context['is_available'] = False

            # Minimum price among available store options (if any)
            first_opt = available_store_products.first()
            context['min_price'] = first_opt.price if first_opt else None
            # Debugging: log key values to help trace availability issues
            try:
                print('PRODUCT_DETAIL_DEBUG', 'slug=', store_product.product.slug, 'selected_zip=', selected_zip,
                      'store_product_id=', store_product.id, 'stock=', getattr(store_product, 'stock_quantity', None),
                      'availability=', getattr(store_product, 'availability_status', None))
            except Exception:
                pass

            # Get related products from all stores in the area
            context['related_products'] = StoreProduct.objects.filter(
                store__in=stores_in_area,
                product__category=store_product.product.category,
                is_available=True
            ).exclude(product=store_product.product).select_related('product', 'store')[:4]

            # Get frequently bought together from all stores
            context['frequently_bought'] = StoreProduct.objects.filter(
                store__in=stores_in_area,
                is_available=True,
                product__category__in=[
                    store_product.product.category,
                ]
            ).exclude(product=store_product.product).select_related('product', 'store')[:3]
        else:
            # Fallback: try to render product-level information even if no StoreProduct is available
            product_slug = self.kwargs.get('product_slug')
            try:
                product = Product.objects.get(slug=product_slug)
                context['product'] = product
            except Product.DoesNotExist:
                context['product'] = None

            # No specific store_product; show any available store options for this product (ignoring zip)
            try:
                available_store_products = StoreProduct.objects.filter(
                    product__slug=product_slug,
                    is_available=True
                ).select_related('store', 'product').order_by('price')
                context['available_stores'] = available_store_products
                context['product_options'] = available_store_products
            except Exception:
                available_store_products = StoreProduct.objects.none()
                context['available_stores'] = StoreProduct.objects.none()
                context['product_options'] = StoreProduct.objects.none()

            # Derive availability by checking store options (ignore zip)
            try:
                context['is_available'] = available_store_products.filter(
                    availability_status='in_stock',
                    stock_quantity__gt=0
                ).exists()
            except Exception:
                context['is_available'] = False

            # Minimum price among these store options
            first_opt = available_store_products.first() if hasattr(available_store_products, 'first') else None
            context['min_price'] = first_opt.price if first_opt else None
            # Debugging: log fallback values
            try:
                print('PRODUCT_DETAIL_DEBUG_FALLBACK', 'slug=', product_slug,
                      'selected_zip=', self.request.session.get('selected_zip_code'),
                      'available_count=', available_store_products.count(),
                      'sample=', [
                          (p.id, getattr(p, 'stock_quantity', None), getattr(p, 'availability_status', None), getattr(p, 'price', None))
                          for p in available_store_products[:3]
                      ])
            except Exception:
                pass

            # Related/frequently bought based on product (if available)
            if context.get('product'):
                context['related_products'] = StoreProduct.objects.filter(
                    product__category=context['product'].category,
                    is_available=True
                ).exclude(product=context['product']).select_related('product', 'store')[:4]

                context['frequently_bought'] = StoreProduct.objects.filter(
                    product__category=context['product'].category,
                    is_available=True
                ).exclude(product=context['product']).select_related('product', 'store')[:3]
            else:
                context['related_products'] = StoreProduct.objects.none()
                context['frequently_bought'] = StoreProduct.objects.none()

        return context

class ProductReviewsView(ListView):
    template_name = 'catalog/product_reviews.html'
    context_object_name = 'reviews'
    paginate_by = 10
    
    def get_queryset(self):
        product_slug = self.kwargs.get('product_slug')
        try:
            product = Product.objects.get(slug=product_slug)
            return ProductReview.objects.filter(
                product=product,
                is_approved=True
            ).select_related('user').order_by('-created_at')
        except Product.DoesNotExist:
            return ProductReview.objects.none()

class AddReviewView(FormView):
    template_name = 'catalog/add_review.html'
    
    def post(self, request, *args, **kwargs):
        # Handle review submission
        return JsonResponse({'success': True, 'message': 'Review submitted successfully!'})

# API Views for AJAX functionality
class ProductDetailsAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        product_id = kwargs.get('product_id')
        store_id = request.session.get('selected_store_id')
        
        if not store_id:
            return JsonResponse({'error': 'No store selected'})
        
        try:
            store_product = StoreProduct.objects.select_related('product').get(
                id=product_id,
                store_id=store_id,
                is_available=True
            )
            
            return JsonResponse({
                'success': True,
                'product': {
                    'id': store_product.id,
                    'name': store_product.product.name,
                    'price': str(store_product.price),
                    'stock': store_product.stock_quantity,
                    'description': store_product.product.description,
                }
            })
        except StoreProduct.DoesNotExist:
            return JsonResponse({'error': 'Product not found'})

class ProductSuggestionsAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        store_id = request.session.get('selected_store_id')
        
        if not store_id or len(query) < 2:
            return JsonResponse({'suggestions': []})
        
        products = StoreProduct.objects.filter(
            store_id=store_id,
            product__name__icontains=query,
            is_available=True
        ).select_related('product')[:5]
        
        suggestions = [
            {
                'id': p.id,
                'name': p.product.name,
                'price': str(p.price)
            }
            for p in products
        ]
        
        return JsonResponse({'suggestions': suggestions})

class AddToCartAPIView(TemplateView):
    def post(self, request, *args, **kwargs):
        """
        Proxy to the orders.add_to_cart_view so catalog pages can add items to cart
        using the same server-side logic and return the same JSON shape.
        """
        try:
            from orders.views import add_to_cart_view
            return add_to_cart_view(request)
        except Exception:
            return JsonResponse({'success': False, 'message': 'Error adding to cart'})

class FilterOptionsAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'filters': {}})
