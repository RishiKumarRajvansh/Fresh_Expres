"""
Enhanced Delivery Workflow Views
Implements the complete workflow as specified:
1. QR code scanning for handover
2. Delivery confirmation via unique code
3. Order status tracking
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
import json

from orders.models import Order
from .models import DeliveryAgent, DeliveryAssignment
from stores.models import Store


@login_required
def scan_handover_code(request):
    """
    Delivery agent enters handover code to confirm handover from store
    """
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            data = json.loads(request.body)
            handover_code = data.get('handover_code')
            
            if not handover_code:
                return JsonResponse({
                    'success': False,
                    'message': 'Handover code is required'
                })
            
            # Find order by handover code
            try:
                order = Order.objects.get(handover_code=handover_code.upper())
            except Order.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid handover code or order not found'
                })
            
            # Verify order is packed and assigned to this agent
            try:
                assignment = DeliveryAssignment.objects.get(
                    order=order,
                    agent=agent,
                    status__in=['assigned', 'accepted']
                )
            except DeliveryAssignment.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Order not assigned to you or invalid status'
                })
            
            if order.status != 'packed':
                return JsonResponse({
                    'success': False,
                    'message': 'Order must be packed before handover'
                })
            
            # Update order and assignment status
            with transaction.atomic():
                order.status = 'handed_to_delivery'
                order.handover_to_delivery_time = timezone.now()
                order.delivery_agent_confirmed = True
                order.save()
                
                assignment.status = 'picked_up'
                assignment.picked_up_at = timezone.now()
                assignment.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Handover confirmed! Order ready for delivery.',
                'order_number': order.order_number,
                'customer_address': str(order.delivery_address),
                'delivery_code': order.delivery_confirmation_code
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error processing handover: {str(e)}'
            })
    
    return render(request, 'delivery/scan_handover.html', {
        'title': 'Enter Handover Code'
    })


@login_required
def confirm_delivery(request):
    """
    Delivery agent enters customer's unique code to confirm delivery
    """
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            data = json.loads(request.body)
            delivery_code = data.get('delivery_code')
            assignment_id = data.get('assignment_id')
            
            if not delivery_code or not assignment_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Delivery code and assignment ID are required'
                })
            
            # Get assignment
            try:
                assignment = DeliveryAssignment.objects.get(
                    id=assignment_id,
                    agent=agent,
                    status='picked_up'
                )
            except DeliveryAssignment.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Assignment not found or invalid status'
                })
            
            order = assignment.order
            
            # Verify delivery code
            if order.delivery_confirmation_code != delivery_code.upper():
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid delivery confirmation code'
                })
            
            # Update order and assignment to delivered
            with transaction.atomic():
                order.status = 'delivered'
                order.actual_delivery_time = timezone.now()
                order.save()
                
                assignment.status = 'delivered'
                assignment.delivered_at = timezone.now()
                assignment.save()
                
                # Update agent stats
                agent.total_deliveries += 1
                agent.successful_deliveries += 1
                agent.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Delivery confirmed successfully!',
                'order_number': order.order_number
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error confirming delivery: {str(e)}'
            })
    
    return render(request, 'delivery/confirm_delivery.html', {
        'title': 'Confirm Delivery'
    })


@login_required
def store_confirm_handover(request):
    """
    Store manager confirms handover to delivery agent
    """
    if request.method == 'POST':
        try:
            if not request.user.user_type == 'business':
                return JsonResponse({
                    'success': False,
                    'message': 'Only store managers can confirm handovers'
                })
            
            data = json.loads(request.body)
            order_id = data.get('order_id')
            verification_code = data.get('verification_code')
            
            if not order_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Order ID is required'
                })
            
            # Get order
            try:
                order = Order.objects.get(
                    id=order_id,
                    store__user=request.user,
                    status='packed'
                )
            except Order.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Order not found or not ready for handover'
                })
            
            # Generate and save verification code if not provided
            if not verification_code:
                import random
                import string
                verification_code = ''.join(random.choices(string.digits, k=4))
                order.handover_verification_code = verification_code
                order.save()
            
            # Update handover confirmation
            with transaction.atomic():
                order.store_handover_confirmed = True
                order.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Handover prepared. Share verification code with delivery agent.',
                'verification_code': order.handover_verification_code,
                'qr_code': order.package_qr_code
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error confirming handover: {str(e)}'
            })
    
    return render(request, 'delivery/store_handover.html', {
        'title': 'Confirm Handover'
    })


@login_required
def order_workflow_status(request, order_number):
    """
    Get comprehensive order workflow status
    """
    try:
        order = get_object_or_404(Order, order_number=order_number)
        
        # Check user permissions
        can_view = False
        if request.user == order.user:  # Customer
            can_view = True
        elif hasattr(request.user, 'store') and request.user.store == order.store:  # Store owner
            can_view = True
        elif hasattr(request.user, 'delivery_agent_profile'):  # Delivery agent
            try:
                assignment = DeliveryAssignment.objects.get(order=order)
                if assignment.agent == request.user.delivery_agent_profile:
                    can_view = True
            except DeliveryAssignment.DoesNotExist:
                pass
        elif request.user.is_staff or request.user.is_superuser:  # Admin
            can_view = True
        
        if not can_view:
            return JsonResponse({
                'success': False,
                'message': 'Permission denied'
            })
        
        # Get workflow status
        workflow_status = {
            'order_number': order.order_number,
            'status': order.status,
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'delivery_confirmation_code': order.delivery_confirmation_code if request.user == order.user or request.user.is_staff else None,
            'package_qr_code': order.package_qr_code if request.user.user_type == 'business' or request.user.is_staff else None,
            'handover_confirmed': {
                'store': order.store_handover_confirmed,
                'delivery_agent': order.delivery_agent_confirmed,
                'time': order.handover_to_delivery_time.isoformat() if order.handover_to_delivery_time else None
            }
        }
        
        # Add assignment info if exists
        try:
            assignment = DeliveryAssignment.objects.get(order=order)
            workflow_status['delivery_assignment'] = {
                'agent_name': assignment.agent.user.get_full_name(),
                'agent_phone': assignment.agent.phone_number,
                'status': assignment.status,
                'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                'picked_up_at': assignment.picked_up_at.isoformat() if assignment.picked_up_at else None,
                'delivered_at': assignment.delivered_at.isoformat() if assignment.delivered_at else None
            }
        except DeliveryAssignment.DoesNotExist:
            workflow_status['delivery_assignment'] = None
        
        return JsonResponse({
            'success': True,
            'workflow_status': workflow_status
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting workflow status: {str(e)}'
        })
