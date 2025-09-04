from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from . import views_loyalty
from . import views_auth

app_name = 'accounts'

urlpatterns = [
    # Customer Authentication (Email-based)
    path('login/', views_auth.CustomerLoginView.as_view(), name='customer_login'),
    path('register/', views_auth.CustomerRegistrationView.as_view(), name='customer_register'),
    
    # Legacy URLs for backward compatibility (redirect to new ones)
    path('phone-login/', views_auth.CustomerLoginView.as_view(), name='phone_login'),
    path('phone-register/', views_auth.CustomerRegistrationView.as_view(), name='phone_register'),
    
    # Email-based Authentication (Admin, Store, Delivery)
    path('email-login/', views_auth.EmailLoginView.as_view(), name='email_login'),
    
    # Business User Registration
    path('business-register/', views_auth.BusinessRegistrationView.as_view(), name='business_register'),
    path('store-register/', views_auth.StoreRegistrationView.as_view(), name='store_register'),
    path('delivery-register/', views_auth.DeliveryAgentRegistrationView.as_view(), name='delivery_register'),
    
    # Password Reset (Non-customer users only)
    path('password-reset/', views_auth.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # Common Authentication
    path('logout/', views_auth.LogoutView.as_view(), name='logout'),
    
    # Profile Management
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    
    # Address Management
    path('addresses/', views.AddressListView.as_view(), name='address_list'),
    path('addresses/add/', views.AddAddressView.as_view(), name='add_address'),
    path('addresses/<int:pk>/edit/', views.EditAddressView.as_view(), name='edit_address'),
    path('addresses/<int:pk>/delete/', views.DeleteAddressView.as_view(), name='delete_address'),
    
    # Wishlist Management
    path('wishlist/', views.WishlistView.as_view(), name='wishlist'),
    path('wishlist/toggle/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/remove/<int:wishlist_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/clear/', views.clear_wishlist, name='clear_wishlist'),
    
    # Loyalty & Rewards System
    path('loyalty/', views_loyalty.loyalty_dashboard, name='loyalty_dashboard'),
    path('loyalty/redeem/<int:reward_id>/', views_loyalty.redeem_reward, name='redeem_reward'),
    path('loyalty/transactions/', views_loyalty.transaction_history, name='transaction_history'),
    path('referral/', views_loyalty.referral_program, name='referral_program'),
]
