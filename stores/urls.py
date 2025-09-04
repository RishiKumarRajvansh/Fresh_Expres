from django.urls import path
from django.shortcuts import redirect
from . import views
from . import views_bulk_import
from . import views_additional
from .order_management_views import (
    StoreOrderDashboardView, StoreOrderListView, StoreOrderDetailView,
    StoreOrderStatusUpdateView, StoreBulkOrderActionsView, store_order_analytics_api
)

app_name = 'stores'

urlpatterns = [
    # Redirect store listing to home (Blinkit-style - no store selection for users)
    path('', lambda request: redirect('core:home'), name='store_list'),
    
    # Store management for store owners - Updated URL names to match dashboard templates
    path('dashboard/', views.StoreDashboardView.as_view(), name='dashboard'),
    
    # Enhanced Order Management System - Primary Routes
    path('orders/', StoreOrderListView.as_view(), name='orders'),
    path('orders/list/', StoreOrderListView.as_view(), name='orders_list'),
    path('orders/management/', StoreOrderListView.as_view(), name='orders_management'),  # Fix for template references
    path('orders/dashboard/', StoreOrderDashboardView.as_view(), name='orders_dashboard'),
    path('orders/<str:order_number>/', StoreOrderDetailView.as_view(), name='order_detail'),
    path('api/orders/update-status/<str:order_number>/', StoreOrderStatusUpdateView.as_view(), name='update_order_status'),
    path('api/orders/bulk-actions/', StoreBulkOrderActionsView.as_view(), name='bulk_order_actions'),
    path('api/orders/analytics/', store_order_analytics_api, name='order_analytics'),
    path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<int:order_id>/refund/', views.process_refund, name='process_refund'),
    path('orders/<int:order_id>/notes/', views.add_order_note, name='add_order_note'),
    

    path('orders/legacy/<int:order_id>/', views.order_detail, name='legacy_order_detail'),
    path('inventory/', views.store_inventory, name='inventory_management'),
    path('inventory/edit/<int:product_id>/', views.edit_store_product, name='edit_product'),
    path('inventory/delete/<int:product_id>/', views.delete_store_product, name='delete_product'),
    path('agents/', views.delivery_agents, name='delivery_agents'),
    
    # Additional store management URLs
    path('profile/', views_additional.store_profile, name='store_profile'),
    path('business-hours/', views_additional.business_hours, name='business_hours'),
    path('analytics/', views_additional.store_analytics, name='analytics'),
    path('create/', views_additional.create_store, name='create_store'),
    
    # Bulk Import System
    path('bulk-import/', views_bulk_import.bulk_import_products, name='bulk_import'),
    path('bulk-import/validate/', views_bulk_import.validate_csv_data, name='validate_csv'),
    path('bulk-import/history/', views_bulk_import.import_history, name='import_history'),
    path('bulk-import/sample-csv/', views_bulk_import.download_sample_csv, name='sample_csv'),
    
    # ZIP Area Management
    path('zip-coverage/', views.manage_zip_coverage, name='manage_zip_coverage'),
    
    # API endpoints for AJAX
    path('api/check-availability/', views.CheckAvailabilityView.as_view(), name='check_availability'),
    path('api/update-inventory/', views.UpdateInventoryView.as_view(), name='update_inventory'),
    path('api/new-orders-count/', views.new_orders_count, name='new_orders_count'),
    path('api/toggle-store-status/', views.toggle_store_status, name='toggle_store_status'),
]
