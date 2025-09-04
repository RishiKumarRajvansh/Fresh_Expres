"""
OTP Handover Views for Order Workflow
Handles Store->Agent and Agent->Customer handovers with OTP verification
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from delivery.models import DeliveryAssignment
from delivery.otp_service import OTPService
from core.decorators import store_required, delivery_agent_required

import logging

logger = logging.getLogger(__name__)

@method_decorator([login_required, store_required], name='dispatch')
class StoreHandoverInitiateView(View):
    """Store staff initiates handover to delivery agent"""
    
    def post(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Verify order is ready for handover
            if order.status != 'packed':
                return JsonResponse({
                    'success': False,
                    'message': 'Order must be packed before handover'
                })
            
            # Check if delivery assignment exists
            if not hasattr(order, 'delivery_assignment'):
                return JsonResponse({
                    'success': False, 
                    'message': 'No delivery agent assigned to this order'
                })
            
            # Generate OTP for handover
            otp = OTPService.create_store_handover_otp(order)
            
            return JsonResponse({
                'success': True,
                'message': 'Store handover OTP generated',
                'otp': otp,
                'agent_name': order.delivery_assignment.agent.user.get_full_name()
            })
            
        except Exception as e:
            logger.error(f"Error initiating store handover: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to generate handover OTP'
            })

@method_decorator([login_required, delivery_agent_required], name='dispatch') 
class AgentHandoverConfirmView(View):
    """Delivery agent confirms receipt from store using OTP"""
    
    def get(self, request, order_id):
        """Show OTP entry form for agent"""
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Verify agent is assigned to this order
            if not hasattr(order, 'delivery_assignment') or order.delivery_assignment.agent.user != request.user:
                messages.error(request, 'You are not assigned to this order')
                return redirect('delivery:agent_orders')
            
            # Check OTP status
            otp_status = OTPService.get_otp_status(order, 'store_handover')
            
            context = {
                'order': order,
                'assignment': order.delivery_assignment,
                'otp_status': otp_status,
                'store': order.store,
            }
            
            return render(request, 'delivery/agent_handover_confirm.html', context)
            
        except Exception as e:
            messages.error(request, 'Error accessing handover page')
            return redirect('delivery:agent_orders')
    
    def post(self, request, order_id):
        """Process OTP verification"""
        try:
            order = get_object_or_404(Order, order_id=order_id)
            otp_entered = request.POST.get('otp')
            
            if not otp_entered:
                return JsonResponse({
                    'success': False,
                    'message': 'Please enter OTP'
                })
            
            # Verify OTP
            success, message = OTPService.verify_store_handover_otp(order, otp_entered)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'Order received from store successfully!',
                    'redirect_url': f'/delivery/orders/'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
                
        except Exception as e:
            logger.error(f"Error verifying store handover OTP: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to verify OTP'
            })

@method_decorator([login_required, delivery_agent_required], name='dispatch')
class CustomerDeliveryInitiateView(View):
    """Agent initiates delivery to customer"""
    
    def post(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Verify agent is assigned and order is ready for delivery
            if not hasattr(order, 'delivery_assignment') or order.delivery_assignment.agent.user != request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'You are not assigned to this order'
                })
            
            if order.status != 'out_for_delivery':
                return JsonResponse({
                    'success': False,
                    'message': 'Order must be out for delivery'
                })
            
            # Generate OTP for customer delivery
            otp = OTPService.create_customer_delivery_otp(order)
            
            # Update assignment status
            assignment = order.delivery_assignment
            assignment.status = 'in_transit'
            assignment.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Customer delivery OTP generated',
                'otp': otp,
                'customer_name': order.user.get_full_name(),
                'customer_phone': getattr(order.user, 'phone', 'N/A')
            })
            
        except Exception as e:
            logger.error(f"Error initiating customer delivery: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to generate delivery OTP'
            })

@method_decorator([login_required, delivery_agent_required], name='dispatch')
class CustomerDeliveryConfirmView(View):
    """Agent confirms delivery to customer using OTP"""
    
    def get(self, request, order_id):
        """Show customer delivery confirmation form"""
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Verify agent is assigned to this order
            if not hasattr(order, 'delivery_assignment') or order.delivery_assignment.agent.user != request.user:
                messages.error(request, 'You are not assigned to this order')
                return redirect('delivery:agent_orders')
            
            # Check OTP status
            otp_status = OTPService.get_otp_status(order, 'customer_delivery')
            
            context = {
                'order': order,
                'assignment': order.delivery_assignment,
                'otp_status': otp_status,
                'customer': order.user,
                'delivery_address': order.delivery_address,
            }
            
            return render(request, 'delivery/customer_delivery_confirm.html', context)
            
        except Exception as e:
            messages.error(request, 'Error accessing delivery confirmation page')
            return redirect('delivery:agent_orders')
    
    def post(self, request, order_id):
        """Process customer delivery OTP verification"""
        try:
            order = get_object_or_404(Order, order_id=order_id)
            otp_entered = request.POST.get('otp')
            delivery_notes = request.POST.get('notes', '')
            
            if not otp_entered:
                return JsonResponse({
                    'success': False,
                    'message': 'Please enter customer OTP'
                })
            
            # Verify OTP
            success, message = OTPService.verify_customer_delivery_otp(order, otp_entered)
            
            if success:
                # Create proof of delivery record
                from delivery.models import ProofOfDelivery
                ProofOfDelivery.objects.create(
                    assignment=order.delivery_assignment,
                    delivery_method='handed_to_customer',
                    customer_name=order.user.get_full_name(),
                    otp_verified=True,
                    otp_code=otp_entered,
                    notes=delivery_notes,
                    delivered_by=request.user
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Order delivered successfully!',
                    'redirect_url': '/delivery/orders/'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': message
                })
                
        except Exception as e:
            logger.error(f"Error verifying customer delivery OTP: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to verify delivery OTP'
            })

@login_required
@csrf_exempt
def generate_handover_otp(request, order_id):
    """API endpoint to generate handover OTP"""
    if request.method == 'POST':
        try:
            order = get_object_or_404(Order, order_id=order_id)
            otp_type = request.POST.get('type')  # 'store_handover' or 'customer_delivery'
            
            if otp_type == 'store_handover':
                otp = OTPService.create_store_handover_otp(order)
            elif otp_type == 'customer_delivery':
                otp = OTPService.create_customer_delivery_otp(order)
            else:
                return JsonResponse({'success': False, 'message': 'Invalid OTP type'})
            
            return JsonResponse({
                'success': True,
                'otp': otp,
                'message': f'{otp_type.replace("_", " ").title()} OTP generated'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required 
@csrf_exempt
def verify_handover_otp(request, order_id):
    """API endpoint to verify handover OTP"""
    if request.method == 'POST':
        try:
            order = get_object_or_404(Order, order_id=order_id)
            otp_entered = request.POST.get('otp')
            otp_type = request.POST.get('type')
            
            if otp_type == 'store_handover':
                success, message = OTPService.verify_store_handover_otp(order, otp_entered)
            elif otp_type == 'customer_delivery':
                success, message = OTPService.verify_customer_delivery_otp(order, otp_entered)
            else:
                return JsonResponse({'success': False, 'message': 'Invalid OTP type'})
            
            return JsonResponse({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})
