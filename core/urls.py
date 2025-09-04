from django.urls import path
from . import views
from .chat_views import FAQListView, chat_start, chat_messages, chat_close
from .contact_views import ImprovedContactView
from .dashboard_views import (
    dashboard_router, CustomerDashboardView, AdminDashboardView,
    StoreDashboardView, DeliveryDashboardView
)

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('zip/', views.ZipCaptureView.as_view(), name='zip_capture'),
    path('zip/change/', views.ChangeZipView.as_view(), name='change_zip'),
    path('waitlist/', views.WaitlistView.as_view(), name='waitlist'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', ImprovedContactView.as_view(), name='contact'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('faq/', FAQListView.as_view(), name='faq'),
    
    # Chat functionality
    path('chat/', views.ChatSupportView.as_view(), name='chat_support'),
    path('chat/start/', chat_start, name='chat_start'),
    path('chat/messages/', chat_messages, name='chat_messages'),
    path('chat/close/', chat_close, name='chat_close'),
    
    # Unified Dashboard System
    path('dashboard/', dashboard_router, name='dashboard_router'),
    path('dashboard/', dashboard_router, name='dashboard'),  # Fallback for templates using 'dashboard' without namespace
    path('dashboard/customer/', CustomerDashboardView.as_view(), name='customer_dashboard'),
    path('dashboard/admin/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/store/', StoreDashboardView.as_view(), name='store_dashboard'),
    path('dashboard/delivery/', DeliveryDashboardView.as_view(), name='delivery_dashboard'),
]
