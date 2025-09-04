from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Customer chat
    path('', views.ChatListView.as_view(), name='chat_list'),
    path('start/', views.StartChatView.as_view(), name='start_chat'),
    path('session/<uuid:session_id>/', views.ChatSessionView.as_view(), name='chat_session'),
    path('session/<uuid:session_id>/close/', views.CloseChatView.as_view(), name='close_chat'),
    path('session/<uuid:session_id>/rate/', views.RateChatView.as_view(), name='rate_chat'),
    
    # Store chat management
    path('store/dashboard/', views.StoreChatDashboardView.as_view(), name='store_chat_dashboard'),
    path('store/session/<uuid:session_id>/', views.StoreChatSessionView.as_view(), name='store_chat_session'),
    path('store/templates/', views.ChatTemplatesView.as_view(), name='chat_templates'),
    path('store/auto-responses/', views.AutoResponsesView.as_view(), name='auto_responses'),
    
    # Admin chat oversight
    path('admin/dashboard/', views.AdminChatDashboardView.as_view(), name='admin_chat_dashboard'),
    path('admin/session/<uuid:session_id>/', views.AdminChatSessionView.as_view(), name='admin_chat_session'),
    path('admin/takeover/', views.TakeoverChatView.as_view(), name='takeover_chat'),
    path('admin/analytics/', views.ChatAnalyticsView.as_view(), name='chat_analytics'),
    
    # API endpoints
    path('api/messages/', views.MessageAPIView.as_view(), name='message_api'),
    path('api/session/<uuid:session_id>/messages/', views.SessionMessagesAPIView.as_view(), name='session_messages_api'),
    path('api/notifications/', views.NotificationsAPIView.as_view(), name='notifications_api'),
    path('api/mark-read/', views.MarkMessagesReadAPIView.as_view(), name='mark_messages_read'),
    
    # File uploads
    path('upload/image/', views.UploadImageView.as_view(), name='upload_image'),
    path('upload/file/', views.UploadFileView.as_view(), name='upload_file'),
]
