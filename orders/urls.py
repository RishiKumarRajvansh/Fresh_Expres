from django.urls import path
from . import views
from .management_views import (
    OrderManagementView, OrderDetailManagementView, OrderStatusUpdateView,
    BulkOrderActionsView, order_analytics_api, OrderDashboardView
)

app_name = 'orders'

urlpatterns = [
    # Cart management - specific paths first
    path('cart/add/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/update/', views.UpdateCartView.as_view(), name='update_cart'),
    path('cart/remove/', views.RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear_cart'),
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/<str:store_code>/', views.StoreCartView.as_view(), name='store_cart'),
    
    # Checkout process
    path('checkout/<str:store_code>/', views.CheckoutView.as_view(), name='checkout'),
    path('checkout/address/', views.CheckoutAddressView.as_view(), name='checkout_address'),
    path('checkout/delivery/', views.CheckoutDeliveryView.as_view(), name='checkout_delivery'),
    path('checkout/payment/', views.CheckoutPaymentView.as_view(), name='checkout_payment'),
    path('checkout/confirmation/', views.CheckoutConfirmationView.as_view(), name='checkout_confirmation'),
    
    # Payment processing
    path('process-payment/<str:order_number>/', views.ProcessPaymentView.as_view(), name='process_payment'),
    
    # Order Management (Enhanced)
    path('dashboard/', OrderDashboardView.as_view(), name='order_dashboard'),
    path('manage/', OrderManagementView.as_view(), name='order_management'),
    path('manage/<str:order_number>/', OrderDetailManagementView.as_view(), name='order_detail_management'),
    path('api/update-status/<str:order_number>/', OrderStatusUpdateView.as_view(), name='update_order_status'),
    path('api/bulk-actions/', BulkOrderActionsView.as_view(), name='bulk_order_actions'),
    path('api/analytics/', order_analytics_api, name='order_analytics_api'),
    
    # Order management (Original)
    path('', views.OrderListView.as_view(), name='order_list'),
    path('<str:order_number>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('<str:order_number>/track/', views.OrderTrackingView.as_view(), name='order_tracking'),
    path('<str:order_number>/cancel/', views.CancelOrderView.as_view(), name='cancel_order'),
    path('<str:order_number>/reorder/', views.ReorderView.as_view(), name='reorder'),
    path('<str:order_number>/rate/', views.RateOrderView.as_view(), name='rate_order'),
    path('<str:order_number>/complaint/', views.FileComplaintView.as_view(), name='file_complaint'),
    path('<str:order_number>/support/', views.OrderSupportView.as_view(), name='order_support'),
    
    # Payment callbacks
    path('payment/success/', views.PaymentSuccessView.as_view(), name='payment_success'),
    path('payment/failure/', views.PaymentFailureView.as_view(), name='payment_failure'),
    path('payment/callback/', views.PaymentCallbackView.as_view(), name='payment_callback'),
    
    # API endpoints
    path('api/delivery-slots/', views.DeliverySlotsAPIView.as_view(), name='delivery_slots_api'),
    path('api/apply-coupon/', views.ApplyCouponAPIView.as_view(), name='apply_coupon_api'),
    path('api/order-status/<str:order_number>/', views.OrderStatusAPIView.as_view(), name='order_status_api'),
]
