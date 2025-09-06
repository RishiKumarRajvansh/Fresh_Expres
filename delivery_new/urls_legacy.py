"""
URL patterns for the delivery_new app with 'delivery' namespace.
This file is imported by the meat_seafood/urls.py file to create a 'delivery' namespace.
"""
from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    # Dashboard views - map to the same views as delivery_new
    path('dashboard/', views.AgentDashboardView.as_view(), name='agent_dashboard'),
    path('agent_dashboard/', views.AgentDashboardView.as_view(), name='dashboard'),
    path('deliveries/', views.DeliveryListView.as_view(), name='delivery_list'),
    path('assignments/', views.DeliveryListView.as_view(), name='assignments'),
    path('agent_orders/', views.DeliveryListView.as_view(), name='agent_orders'),
    path('delivery/<int:pk>/', views.DeliveryDetailView.as_view(), name='delivery_detail'),
    path('assignment/<int:pk>/', views.DeliveryDetailView.as_view(), name='assignment_detail'),
    
    # Delivery actions
    path('delivery/<int:pk>/accept/', views.AcceptDeliveryView.as_view(), name='accept_delivery'),
    path('accept_order/<int:pk>/', views.AcceptDeliveryView.as_view(), name='accept_order'),
    path('delivery/<int:pk>/arrive-at-store/', views.ArriveAtStoreView.as_view(), name='arrive_at_store'),
    path('delivery/<int:pk>/verify-store-pickup/', views.VerifyStorePickupView.as_view(), name='verify_store_pickup'),
    path('pickup_order/<int:pk>/', views.VerifyStorePickupView.as_view(), name='pickup_order'),
    path('delivery/<int:pk>/start-transit/', views.StartTransitView.as_view(), name='start_transit'),
    path('delivery/<int:pk>/verify-customer-delivery/', views.VerifyCustomerDeliveryView.as_view(), name='verify_customer_delivery'),
    path('deliver_order/<int:pk>/', views.VerifyCustomerDeliveryView.as_view(), name='deliver_order'),
    path('delivery/<int:pk>/report-issue/', views.ReportDeliveryIssueView.as_view(), name='report_issue'),
    path('delivery/<int:pk>/cancel/', views.CancelDeliveryView.as_view(), name='cancel_delivery'),
    
    # Agent profile and settings
    path('profile/', views.AgentProfileView.as_view(), name='agent_profile'),
    path('agent_profile/', views.AgentProfileView.as_view(), name='agent_profile_new'),
    path('earnings/', views.AgentEarningsView.as_view(), name='earnings'),
    path('history/', views.DeliveryListView.as_view(), name='delivery_history'),
    path('ratings/', views.AgentProfileView.as_view(), name='ratings_feedback'),
    path('vehicle-info/', views.AgentProfileView.as_view(), name='vehicle_info'),
    
    # API endpoints for mobile app
    path('api/toggle-availability/', views.ToggleAvailabilityAPIView.as_view(), name='toggle_availability'),
    path('api/update-location/', views.UpdateLocationAPIView.as_view(), name='update_location'),
    
    # Customer-facing views
    path('track/<slug:delivery_id>/', views.TrackDeliveryView.as_view(), name='track_order'),
]
