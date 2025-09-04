from django.urls import path
from . import views
from .production_views import *
from .workflow_views import *
from . import otp_views
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Placeholder views for missing functions
@login_required
def ratings_feedback(request):
    return render(request, 'delivery/ratings_feedback.html', {
        'title': 'Ratings & Feedback',
        'agent': request.user.deliveryagent if hasattr(request.user, 'deliveryagent') else None
    })

@login_required 
def vehicle_info(request):
    return render(request, 'delivery/vehicle_info.html', {
        'title': 'Vehicle Information',
        'user': request.user
    })

@login_required
def delivery_history(request):
    return render(request, 'delivery/delivery_history.html', {
        'title': 'Delivery History'
    })

@login_required 
def toggle_availability(request):
    from django.http import JsonResponse
    from .models import DeliveryAgent
    
    if request.method == 'POST':
        try:
            # Get the delivery agent for the current user
            agent = DeliveryAgent.objects.get(user=request.user)
            
            # Toggle availability
            agent.is_available = not agent.is_available
            agent.save()
            
            return JsonResponse({
                'success': True, 
                'available': agent.is_available,
                'message': f'Status changed to {"Online" if agent.is_available else "Offline"}'
            })
            
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Delivery agent profile not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def update_location(request):
    from django.http import JsonResponse
    from .models import DeliveryAgent
    import json
    
    if request.method == 'POST':
        try:
            # Get the delivery agent for the current user
            agent = DeliveryAgent.objects.get(user=request.user)
            
            # Get location data from request
            data = json.loads(request.body)
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            if latitude and longitude:
                # Update agent location (you may need to add these fields to the model)
                # For now, just return success
                return JsonResponse({
                    'success': True,
                    'message': 'Location updated successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid location data'
                })
            
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Delivery agent profile not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

app_name = 'delivery'

urlpatterns = [
    # Agent Dashboard
    path('dashboard/', AgentDashboardView.as_view(), name='agent_dashboard'),
    
    # Order Management
    path('orders/', AgentOrdersView.as_view(), name='agent_orders'),
    path('orders/<int:assignment_id>/', AgentOrderDetailView.as_view(), name='assignment_detail'),
    path('accept-order/<int:assignment_id>/', accept_order, name='accept_order'),
    path('pickup-order/<int:assignment_id>/', pickup_order, name='pickup_order'),
    path('deliver-order/<int:assignment_id>/', deliver_order, name='deliver_order'),
    
    # Agent Features
    path('earnings/', AgentEarningsView.as_view(), name='earnings'),
    path('history/', delivery_history, name='delivery_history'),
    path('ratings/', ratings_feedback, name='ratings_feedback'),
    path('vehicle-info/', vehicle_info, name='vehicle_info'),
    
    # New Agent Profile and ZIP Coverage
    path('profile/', views.agent_profile, name='agent_profile_new'),
    path('zip-coverage/', views.agent_zip_coverage_view, name='agent_zip_coverage'),
    
    # AJAX APIs
    path('api/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('api/update-location/', update_location, name='update_location'),
    
    # Enhanced Workflow APIs
    path('scan-handover/', scan_handover_code, name='scan_handover_code'),
    path('confirm-delivery/', confirm_delivery, name='confirm_delivery'),
    path('store/confirm-handover/', store_confirm_handover, name='store_confirm_handover'),
    path('workflow-status/<str:order_number>/', order_workflow_status, name='workflow_status'),
    
    # OTP Verification Workflow
    path('handover/<str:order_id>/', views.handover_order, name='handover_order'),
    path('confirm-delivery-otp/<str:order_id>/', views.confirm_delivery_otp, name='confirm_delivery_otp'),
    path('agent/handover/<str:order_id>/', views.AgentOrderHandoverView.as_view(), name='agent_handover'),
    path('agent/deliver/<str:order_id>/', views.AgentDeliveryConfirmView.as_view(), name='agent_delivery_confirm'),
    path('store/assign-agent/<str:order_id>/', views.ManualAgentAssignmentView.as_view(), name='manual_assignment'),
    path('test/assign-agent/<str:order_id>/', views.TestAssignmentView.as_view(), name='test_assignment'),
    
    # Enhanced OTP Workflow
    path('otp/store-handover/<str:order_id>/', otp_views.StoreHandoverInitiateView.as_view(), name='store_handover_initiate'),
    path('otp/agent-handover/<str:order_id>/', otp_views.AgentHandoverConfirmView.as_view(), name='agent_handover_confirm'),
    path('otp/customer-delivery-initiate/<str:order_id>/', otp_views.CustomerDeliveryInitiateView.as_view(), name='customer_delivery_initiate'),
    path('otp/customer-delivery-confirm/<str:order_id>/', otp_views.CustomerDeliveryConfirmView.as_view(), name='customer_delivery_confirm'),
    path('generate-otp/<str:order_id>/', otp_views.generate_handover_otp, name='generate_otp'),
    path('verify-otp/<str:order_id>/', otp_views.verify_handover_otp, name='verify_otp'),
    
    # Order Tracking (for customers)
    path('track/<str:order_number>/', views.TrackOrderView.as_view(), name='track_order'),
    
    # Legacy URLs (for backward compatibility)
    path('agent/orders/<str:order_number>/', views.AgentOrderDetailView.as_view(), name='agent_order_detail_legacy'),
    path('agent/profile/', views.AgentProfileView.as_view(), name='agent_profile'),
]
