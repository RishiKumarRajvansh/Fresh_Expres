from django.urls import path
from . import views, views_phonepe

app_name = 'payments'

urlpatterns = [
    path('methods/', views.payment_methods, name='payment_methods'),
    path('add/', views.add_payment_method, name='add_payment_method'),
    path('delete/<int:method_id>/', views.delete_payment_method, name='delete_payment_method'),
    path('set-default/<int:method_id>/', views.set_default_payment_method, name='set_default_payment_method'),
    path('checkout-options/', views.payment_options_checkout, name='checkout_options'),
    
    # PhonePe Integration
    path('phonepe/initiate/', views_phonepe.initiate_phonepe_payment, name='phonepe_initiate'),
    path('phonepe/callback/', views_phonepe.phonepe_callback, name='phonepe_callback'),
    path('phonepe/webhook/', views_phonepe.phonepe_webhook, name='phonepe_webhook'),
    path('phonepe/refund-webhook/', views_phonepe.phonepe_refund_webhook, name='phonepe_refund_webhook'),
    path('status/<str:transaction_id>/', views_phonepe.payment_status_check, name='payment_status'),
    
    # Legacy URLs (commented out - other gateways disabled)
    # path('razorpay/callback/', views.razorpay_callback, name='razorpay_callback'),
    path('upi/qr/', views.upi_qr_payment, name='upi_qr_payment'),
]
