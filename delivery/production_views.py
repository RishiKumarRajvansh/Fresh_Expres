from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import PermissionDenied
from decimal import Decimal
import json
from .models import DeliveryAgent, DeliveryAssignment, DeliveryTracking, ProofOfDelivery
from orders.models import Order
from stores.models import Store

# Agent Dashboard Views
class AgentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            agent = self.request.user.delivery_agent_profile
            
            # Get today's stats
            today = timezone.now().date()
            assignments_today = DeliveryAssignment.objects.filter(
                agent=agent,
                assigned_at__date=today
            )
            
            context.update({
                'agent': agent,
                'total_orders_today': assignments_today.count(),
                'completed_orders_today': assignments_today.filter(status='delivered').count(),
                'pending_orders': assignments_today.filter(status__in=['assigned', 'accepted', 'picked_up']).count(),
                'total_earnings_today': self.calculate_earnings(assignments_today.filter(status='delivered')),
                'current_orders': assignments_today.filter(status__in=['assigned', 'accepted', 'picked_up'])[:5],
                'agent_status': agent.status,
                'is_available': agent.is_available,
            })
            
        except DeliveryAgent.DoesNotExist:
            context['agent'] = None
            
        return context
    
    def calculate_earnings(self, assignments):
        total = Decimal('0.00')
        for assignment in assignments:
            # Basic delivery fee calculation
            total += Decimal('50.00')  # Base delivery fee
            if assignment.estimated_distance_km:
                total += assignment.estimated_distance_km * Decimal('5.00')  # Per km rate
        return total

class AgentOrdersView(LoginRequiredMixin, ListView):
    template_name = 'delivery/agent_orders.html'
    context_object_name = 'assignments'
    paginate_by = 20
    
    def get_queryset(self):
        try:
            agent = self.request.user.delivery_agent_profile
            status_filter = self.request.GET.get('status', 'all')
            
            queryset = DeliveryAssignment.objects.filter(agent=agent).select_related('order', 'order__user')
            
            if status_filter != 'all':
                queryset = queryset.filter(status=status_filter)
                
            return queryset.order_by('-assigned_at')
        except DeliveryAgent.DoesNotExist:
            return DeliveryAssignment.objects.none()

class AgentOrderDetailView(LoginRequiredMixin, DetailView):
    model = DeliveryAssignment
    template_name = 'delivery/agent_order_detail.html'
    context_object_name = 'assignment'
    
    def get_object(self, queryset=None):
        assignment = super().get_object(queryset)
        # Ensure agent can only view their own assignments
        if assignment.agent.user != self.request.user:
            raise PermissionDenied
        return assignment

# Order Status Management Views
@login_required
def accept_order(request, assignment_id):
    """Agent accepts an assigned order"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, agent=agent)
            
            if assignment.status == 'assigned':
                with transaction.atomic():
                    assignment.status = 'accepted'
                    assignment.accepted_at = timezone.now()
                    assignment.save()
                    
                    # Update order status
                    assignment.order.status = 'accepted'
                    assignment.order.save()
                    
                return JsonResponse({
                    'success': True,
                    'message': 'Order accepted successfully',
                    'status': 'accepted'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Order cannot be accepted in current status'
                })
                
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Agent profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def pickup_order(request, assignment_id):
    """Agent marks order as picked up from store"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, agent=agent)
            
            if assignment.status == 'accepted':
                with transaction.atomic():
                    assignment.status = 'picked_up'
                    assignment.picked_up_at = timezone.now()
                    assignment.save()
                    
                    # Update order status
                    assignment.order.status = 'out_for_delivery'
                    assignment.order.save()
                    
                return JsonResponse({
                    'success': True,
                    'message': 'Order picked up successfully',
                    'status': 'picked_up'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Order must be accepted first'
                })
                
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Agent profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def deliver_order(request, assignment_id):
    """Agent completes delivery with proof"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, agent=agent)
            
            if assignment.status == 'picked_up':
                # Get delivery proof data
                delivery_method = request.POST.get('delivery_method')
                recipient_name = request.POST.get('recipient_name')
                notes = request.POST.get('notes', '')
                delivery_photo = request.FILES.get('delivery_photo')
                customer_signature = request.POST.get('customer_signature')
                
                with transaction.atomic():
                    # Create proof of delivery
                    proof = ProofOfDelivery.objects.create(
                        assignment=assignment,
                        delivery_method=delivery_method,
                        recipient_name=recipient_name,
                        delivery_photo=delivery_photo,
                        customer_signature_data=customer_signature,
                        agent_notes=notes,
                        delivered_by=agent.user
                    )
                    
                    # Update assignment
                    assignment.status = 'delivered'
                    assignment.delivered_at = timezone.now()
                    
                    # Calculate actual delivery time
                    if assignment.picked_up_at:
                        time_diff = timezone.now() - assignment.picked_up_at
                        assignment.actual_time_minutes = int(time_diff.total_seconds() / 60)
                    
                    assignment.save()
                    
                    # Update order status
                    assignment.order.status = 'delivered'
                    assignment.order.delivered_at = timezone.now()
                    assignment.order.save()
                    
                return JsonResponse({
                    'success': True,
                    'message': 'Order delivered successfully',
                    'status': 'delivered'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Order must be picked up first'
                })
                
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Agent profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def update_location(request):
    """Update agent's current location for tracking"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            data = json.loads(request.body)
            
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            speed_kmh = data.get('speed_kmh')
            battery_level = data.get('battery_level')
            
            if not (latitude and longitude):
                return JsonResponse({'success': False, 'message': 'Location data required'})
            
            # Find active assignments
            active_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                status__in=['accepted', 'picked_up']
            )
            
            # Create tracking points for each active assignment
            for assignment in active_assignments:
                DeliveryTracking.objects.create(
                    assignment=assignment,
                    latitude=Decimal(str(latitude)),
                    longitude=Decimal(str(longitude)),
                    speed_kmh=Decimal(str(speed_kmh)) if speed_kmh else None,
                    battery_level=battery_level
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Location updated successfully'
            })
            
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Agent profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def toggle_availability(request):
    """Toggle agent's availability status"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            
            # Toggle availability
            agent.is_available = not agent.is_available
            
            # Update status based on availability
            if agent.is_available:
                agent.status = 'active'
            else:
                agent.status = 'offline'
                
            agent.save()
            
            return JsonResponse({
                'success': True,
                'is_available': agent.is_available,
                'status': agent.status,
                'message': f'Status updated to {agent.get_status_display()}'
            })
            
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Agent profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

# Public Tracking API
def tracking_api(request, order_number):
    """Public API for customers to track their orders"""
    try:
        order = get_object_or_404(Order, order_number=order_number)
        
        # Check if order has delivery assignment
        try:
            assignment = order.delivery_assignment
            
            # Get latest tracking point
            latest_tracking = assignment.tracking_points.first()
            
            response_data = {
                'order_number': order.order_number,
                'status': order.get_status_display(),
                'delivery_status': assignment.get_status_display(),
                'agent_name': assignment.agent.user.get_full_name(),
                'agent_phone': assignment.agent.phone_number,
                'estimated_time': assignment.estimated_time_minutes,
            }
            
            if latest_tracking:
                response_data.update({
                    'current_location': {
                        'latitude': float(latest_tracking.latitude),
                        'longitude': float(latest_tracking.longitude),
                        'last_updated': latest_tracking.created_at.isoformat(),
                    }
                })
            
            # Add timeline
            timeline = []
            if assignment.assigned_at:
                timeline.append({
                    'status': 'Order Assigned',
                    'timestamp': assignment.assigned_at.isoformat(),
                    'description': 'Order assigned to delivery agent'
                })
            if assignment.accepted_at:
                timeline.append({
                    'status': 'Order Accepted',
                    'timestamp': assignment.accepted_at.isoformat(),
                    'description': 'Agent accepted the order'
                })
            if assignment.picked_up_at:
                timeline.append({
                    'status': 'Order Picked Up',
                    'timestamp': assignment.picked_up_at.isoformat(),
                    'description': 'Order picked up from store'
                })
            if assignment.delivered_at:
                timeline.append({
                    'status': 'Order Delivered',
                    'timestamp': assignment.delivered_at.isoformat(),
                    'description': 'Order successfully delivered'
                })
            
            response_data['timeline'] = timeline
            
            return JsonResponse(response_data)
            
        except DeliveryAssignment.DoesNotExist:
            return JsonResponse({
                'order_number': order.order_number,
                'status': order.get_status_display(),
                'message': 'No delivery assignment found'
            })
            
    except Order.DoesNotExist:
        return JsonResponse({
            'error': 'Order not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

# Agent Profile and Earnings
class AgentProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['agent'] = self.request.user.delivery_agent_profile
        except DeliveryAgent.DoesNotExist:
            context['agent'] = None
        return context

class AgentEarningsView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_earnings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            agent = self.request.user.delivery_agent_profile
            
            # Calculate earnings for different periods
            today = timezone.now().date()
            week_start = today - timezone.timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            
            delivered_orders = DeliveryAssignment.objects.filter(
                agent=agent,
                status='delivered'
            )
            
            context.update({
                'agent': agent,
                'today_earnings': self.calculate_period_earnings(delivered_orders, today, today),
                'week_earnings': self.calculate_period_earnings(delivered_orders, week_start, today),
                'month_earnings': self.calculate_period_earnings(delivered_orders, month_start, today),
                'total_deliveries': delivered_orders.count(),
                'recent_deliveries': delivered_orders.order_by('-delivered_at')[:10]
            })
            
        except DeliveryAgent.DoesNotExist:
            context['agent'] = None
            
        return context
    
    def calculate_period_earnings(self, queryset, start_date, end_date):
        orders = queryset.filter(delivered_at__date__range=[start_date, end_date])
        total = Decimal('0.00')
        for assignment in orders:
            total += Decimal('50.00')  # Base delivery fee
            if assignment.estimated_distance_km:
                total += assignment.estimated_distance_km * Decimal('5.00')
        return {
            'amount': total,
            'count': orders.count()
        }

# Additional views for the URL patterns

@login_required
def agent_orders(request):
    """Display all orders for the agent"""
    try:
        agent = DeliveryAgent.objects.get(user=request.user)
        assignments = DeliveryAssignment.objects.filter(
            agent=agent
        ).order_by('-assigned_at')[:20]  # Last 20 orders
        
        context = {
            'agent': agent,
            'assignments': assignments,
        }
        return render(request, 'delivery/agent_orders.html', context)
        
    except DeliveryAgent.DoesNotExist:
        return redirect('delivery:agent_dashboard')

@login_required
def delivery_history(request):
    """Display delivery history for the agent"""
    try:
        agent = DeliveryAgent.objects.get(user=request.user)
        assignments = DeliveryAssignment.objects.filter(
            agent=agent,
            status__in=['delivered', 'cancelled']
        ).order_by('-delivered_at')[:50]  # Last 50 completed orders
        
        context = {
            'agent': agent,
            'assignments': assignments,
        }
        return render(request, 'delivery/delivery_history.html', context)
        
    except DeliveryAgent.DoesNotExist:
        return redirect('delivery:agent_dashboard')

@login_required
def earnings_report(request):
    """Display earnings report for the agent"""
    try:
        agent = DeliveryAgent.objects.get(user=request.user)
        
        # Calculate different time period earnings
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Today's earnings
        today_assignments = DeliveryAssignment.objects.filter(
            agent=agent,
            status='delivered',
            delivered_at__date=today
        )
        today_earnings = sum(a.delivery_fee or Decimal('50.00') for a in today_assignments)
        
        # This week's earnings
        week_assignments = DeliveryAssignment.objects.filter(
            agent=agent,
            status='delivered',
            delivered_at__date__gte=week_start
        )
        week_earnings = sum(a.delivery_fee or Decimal('50.00') for a in week_assignments)
        
        # This month's earnings
        month_assignments = DeliveryAssignment.objects.filter(
            agent=agent,
            status='delivered',
            delivered_at__date__gte=month_start
        )
        month_earnings = sum(a.delivery_fee or Decimal('50.00') for a in month_assignments)
        
        context = {
            'agent': agent,
            'today_earnings': today_earnings,
            'today_deliveries': today_assignments.count(),
            'week_earnings': week_earnings,
            'week_deliveries': week_assignments.count(),
            'month_earnings': month_earnings,
            'month_deliveries': month_assignments.count(),
        }
        return render(request, 'delivery/earnings_report.html', context)
        
    except DeliveryAgent.DoesNotExist:
        return redirect('delivery:agent_dashboard')

# Admin functions (placeholder for future implementation)
@staff_member_required
def admin_assignments(request):
    """Admin view for all delivery assignments"""
    assignments = DeliveryAssignment.objects.all().order_by('-assigned_at')[:100]
    return render(request, 'admin/delivery/assignments.html', {'assignments': assignments})

@staff_member_required 
def admin_agents(request):
    """Admin view for all delivery agents"""
    agents = DeliveryAgent.objects.all()
    return render(request, 'admin/delivery/agents.html', {'agents': agents})

@staff_member_required
def admin_analytics(request):
    """Admin analytics dashboard"""
    # Calculate platform-wide statistics
    total_orders = DeliveryAssignment.objects.count()
    completed_orders = DeliveryAssignment.objects.filter(status='delivered').count()
    active_agents = DeliveryAgent.objects.filter(is_available=True).count()
    
    context = {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
        'active_agents': active_agents,
    }
    return render(request, 'admin/delivery/analytics.html', context)
