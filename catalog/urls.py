from django.urls import path
from . import views
from . import views_suggestions

app_name = 'catalog'

urlpatterns = [
    # Product listing and search
    path('', views.ProductListView.as_view(), name='product_list'),
    path('category/<slug:category_slug>/', views.CategoryProductsView.as_view(), name='category_products'),
    path('category/<int:category_id>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('search/', views.ProductSearchView.as_view(), name='product_search'),
    
    # Product details
    path('product/<slug:product_slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<slug:product_slug>/reviews/', views.ProductReviewsView.as_view(), name='product_reviews'),
    path('product/<slug:product_slug>/review/add/', views.AddReviewView.as_view(), name='add_review'),
    
    # AJAX endpoints
    path('api/product/<int:store_product_id>/details/', views.ProductDetailsAPIView.as_view(), name='product_details_api'),
    path('api/suggestions/<int:product_id>/', views.ProductSuggestionsAPIView.as_view(), name='product_suggestions'),
    path('api/add-to-cart/', views.AddToCartAPIView.as_view(), name='add_to_cart_api'),
    
    # Product Suggestions & "Complete the Dish"
    path('api/product-suggestions/<int:store_product_id>/', views_suggestions.get_product_suggestions, name='enhanced_product_suggestions'),
    path('api/complete-dish/<int:product_id>/', views_suggestions.complete_dish_suggestions, name='complete_dish'),
    path('api/add-suggestions-to-cart/', views_suggestions.add_suggestion_to_cart, name='add_suggestions_to_cart'),
    
    # Filters and facets
    path('api/filters/', views.FilterOptionsAPIView.as_view(), name='filter_options'),
]
