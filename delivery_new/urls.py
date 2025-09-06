from django.urls import path
from . import views

app_name = 'delivery_new'

urlpatterns = [
    # Dashboard views
    path('dashboard/', views.AgentDashboardView.as_view(), name='dashboard'),
    path('deliveries/', views.DeliveryListView.as_view(), name='delivery_list'),
    path('delivery/<int:pk>/', views.DeliveryDetailView.as_view(), name='delivery_detail'),
    
    # Delivery actions
    path('delivery/<int:pk>/accept/', views.AcceptDeliveryView.as_view(), name='accept_delivery'),
    path('delivery/<int:pk>/arrive-at-store/', views.ArriveAtStoreView.as_view(), name='arrive_at_store'),
    path('delivery/<int:pk>/verify-store-pickup/', views.VerifyStorePickupView.as_view(), name='verify_store_pickup'),
    path('delivery/<int:pk>/start-transit/', views.StartTransitView.as_view(), name='start_transit'),
    path('delivery/<int:pk>/verify-customer-delivery/', views.VerifyCustomerDeliveryView.as_view(), name='verify_customer_delivery'),
    path('delivery/<int:pk>/report-issue/', views.ReportDeliveryIssueView.as_view(), name='report_issue'),
    path('delivery/<int:pk>/cancel/', views.CancelDeliveryView.as_view(), name='cancel_delivery'),
    
    # Agent profile and settings
    path('profile/', views.AgentProfileView.as_view(), name='agent_profile'),
    path('profile/service-areas/', views.AgentZipCoverageView.as_view(), name='agent_zip_coverage'),
    path('earnings/', views.AgentEarningsView.as_view(), name='agent_earnings'),
    path('ratings/', views.RatingsFeedbackView.as_view(), name='ratings_feedback'),
    
    # API endpoints for mobile app
    path('api/toggle-availability/', views.ToggleAvailabilityAPIView.as_view(), name='toggle_availability_api'),
    path('api/update-location/', views.UpdateLocationAPIView.as_view(), name='update_location_api'),
    
    # Customer-facing views
    path('track/<slug:delivery_id>/', views.TrackDeliveryView.as_view(), name='track_delivery'),
    path('rate/<slug:delivery_id>/', views.SubmitDeliveryRatingView.as_view(), name='submit_rating'),
]
