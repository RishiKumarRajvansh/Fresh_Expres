from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.views import View
from core.decorators import DeliveryAgentRequiredMixin, StoreRequiredMixin

# Import models
from .models import DeliveryAgent, DeliveryAssignment
from orders.models import Order
from stores.models import Store
from .services import DeliveryAssignmentService

class AgentDashboardView(DeliveryAgentRequiredMixin, TemplateView):
    template_name = 'delivery/agent_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            # Get the delivery agent profile
            agent = DeliveryAgent.objects.get(user=user)
            
            # Get dashboard statistics
            today_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                assigned_at__date=timezone.now().date()
            )
            
            pending_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                status__in=['assigned', 'accepted', 'picked_up', 'in_transit']
            ).select_related('order', 'order__user', 'order__store')
            
            completed_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                status='delivered'
            )
            
            context.update({
                'agent': agent,
                'active_assignments': pending_assignments,
                'stats': {
                    'total_assignments': DeliveryAssignment.objects.filter(agent=agent).count(),
                    'completed': completed_assignments.count(),
                    'completion_rate': (completed_assignments.count() / max(1, DeliveryAssignment.objects.filter(agent=agent).count())) * 100,
                    'avg_delivery_time': 45  # Placeholder - can be calculated from actual delivery times
                }
            })
            
        except DeliveryAgent.DoesNotExist:
            context.update({
                'agent': None,
                'active_assignments': [],
                'stats': {
                    'total_assignments': 0,
                    'completed': 0,
                    'completion_rate': 0,
                    'avg_delivery_time': 0
                }
            })
        
        return context

class AgentOrdersView(DeliveryAgentRequiredMixin, ListView):
    template_name = 'delivery/agent_orders.html'
    context_object_name = 'orders'
    
    def get_queryset(self):
        """Get orders assigned to the current delivery agent"""
        try:
            agent = DeliveryAgent.objects.get(user=self.request.user)
            # Get orders through delivery assignments
            assignments = DeliveryAssignment.objects.filter(
                agent=agent
            ).select_related('order', 'order__user', 'order__store').order_by('-assigned_at')
            
            return assignments
        except DeliveryAgent.DoesNotExist:
            return DeliveryAssignment.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            print(f"DEBUG: Looking for agent with user: {self.request.user.email} (id: {self.request.user.id})")
            agent = DeliveryAgent.objects.get(user=self.request.user)
            print(f"DEBUG: Found agent: {agent.agent_id}")
            context['agent'] = agent
            
            # Get counts for different statuses
            assignments = self.get_queryset()
            context['pending_count'] = assignments.filter(status__in=['assigned', 'accepted']).count()
            context['active_count'] = assignments.filter(status__in=['picked_up', 'in_transit']).count()
            context['completed_count'] = assignments.filter(status='delivered').count()
            
            print(f"DEBUG: Orders count: {len(assignments)}")
            
        except DeliveryAgent.DoesNotExist:
            context['agent'] = None
            context['pending_count'] = 0
            context['active_count'] = 0
            context['completed_count'] = 0
            
        return context

class AgentOrderDetailView(LoginRequiredMixin, DetailView):
    template_name = 'delivery/agent_order_detail.html'
    context_object_name = 'order'

class AgentProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_profile.html'

class AgentEarningsView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_earnings.html'

class AcceptOrderView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class PickupOrderView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/pickup_order.html'

class DeliverOrderView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/deliver_order.html'

class ProofOfDeliveryView(LoginRequiredMixin, FormView):
    template_name = 'delivery/proof_of_delivery.html'

class UpdateLocationView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class ToggleAvailabilityView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class TrackOrderView(TemplateView):
    """Track order for customers"""
    template_name = 'delivery/track_order.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_number = kwargs.get('order_number')
        context['order_number'] = order_number
        context['title'] = f'Track Order #{order_number}'
        return context

class TrackingAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'location': {'lat': 0, 'lng': 0}})

class AgentLocationAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'location': {'lat': 0, 'lng': 0}})

class DeliveryZonesAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'zones': []})

class OptimizeRouteAPIView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'route': []})


# New delivery agent profile views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from .models import DeliveryAgentZipCoverage
from stores.forms import DeliveryAgentZipCoverageForm
from locations.models import ZipArea


@login_required
def agent_profile(request):
    """Delivery agent profile and dashboard"""
    try:
        agent = request.user.delivery_agent_profile
    except:
        messages.error(request, 'You must be a registered delivery agent to access this page.')
        return redirect('core:home')
    
    # Get agent's current coverage areas
    current_coverage = agent.zip_coverages.filter(is_active=True).select_related('zip_area')
    
    # Get recent delivery stats (you can expand this)
    context = {
        'agent': agent,
        'current_coverage': current_coverage,
        'coverage_count': current_coverage.count(),
    }
    
    return render(request, 'delivery/agent_profile.html', context)


@login_required
def agent_zip_coverage_view(request):
    """View for delivery agents to select ZIP areas they can serve"""
    try:
        agent = request.user.delivery_agent_profile
    except:
        messages.error(request, 'You must be a registered delivery agent to access this page.')
        return redirect('core:home')
    
    if request.method == 'POST':
        form = DeliveryAgentZipCoverageForm(request.POST, agent=agent)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service area updated successfully!')
            return redirect('delivery:agent_zip_coverage')
    else:
        form = DeliveryAgentZipCoverageForm(agent=agent)
    
    context = {
        'agent': agent,
        'form': form,
        'current_coverage': agent.zip_coverages.filter(is_active=True).select_related('zip_area'),
    }
    
    return render(request, 'delivery/agent_zip_coverage.html', context)


@login_required
def toggle_availability(request):
    """AJAX endpoint to toggle agent availability"""
    if request.method == 'POST':
        try:
            agent = request.user.delivery_agent_profile
            agent.is_available = not agent.is_available
            agent.save()
            
            return JsonResponse({
                'success': True,
                'is_available': agent.is_available,
                'message': f'You are now {"available" if agent.is_available else "offline"}'
            })
        except:
            return JsonResponse({
                'success': False,
                'message': 'Agent profile not found'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


@csrf_exempt
@require_http_methods(["POST"])
def handover_order(request, order_id):
    """Handle store-to-agent handover with OTP verification"""
    try:
        order = get_object_or_404(Order, order_number=order_id)
        handover_code = request.POST.get('handover_code')
        
        if not handover_code:
            return JsonResponse({
                'success': False,
                'message': 'Handover code is required'
            })
        
        success, message = DeliveryAssignmentService.handover_to_agent(order, handover_code)
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def confirm_delivery_otp(request, order_id):
    """Handle final delivery confirmation with customer OTP"""
    try:
        order = get_object_or_404(Order, order_number=order_id)
        delivery_code = request.POST.get('delivery_code')
        
        if not delivery_code:
            return JsonResponse({
                'success': False,
                'message': 'Delivery confirmation code is required'
            })
        
        success, message = DeliveryAssignmentService.confirm_delivery(order, delivery_code)
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


class AgentOrderHandoverView(DeliveryAgentRequiredMixin, TemplateView):
    """View for agent to scan/enter handover OTP"""
    template_name = 'delivery/handover_order.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        
        try:
            order = get_object_or_404(Order, order_number=order_id)
            assignment = order.delivery_assignment
            
            # Verify this agent is assigned to this order
            if assignment.agent.user != self.request.user:
                messages.error(self.request, "You are not assigned to this order")
                return context
            
            context.update({
                'order': order,
                'assignment': assignment,
            })
            
        except DeliveryAssignment.DoesNotExist:
            messages.error(self.request, "No delivery assignment found for this order")
        
        return context


class AgentDeliveryConfirmView(DeliveryAgentRequiredMixin, TemplateView):
    """View for agent to confirm final delivery with customer OTP"""
    template_name = 'delivery/confirm_delivery.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        
        try:
            order = get_object_or_404(Order, order_number=order_id)
            assignment = order.delivery_assignment
            
            # Verify this agent is assigned to this order
            if assignment.agent.user != self.request.user:
                messages.error(self.request, "You are not assigned to this order")
                return context
            
            # Verify order has been picked up
            if assignment.status != 'picked_up':
                messages.error(self.request, "Order must be picked up before delivery")
                return context
            
            context.update({
                'order': order,
                'assignment': assignment,
            })
            
        except DeliveryAssignment.DoesNotExist:
            messages.error(self.request, "No delivery assignment found for this order")
        
        return context


@method_decorator(csrf_exempt, name='dispatch')
class ManualAgentAssignmentView(LoginRequiredMixin, TemplateView):
    """View for store managers to manually assign delivery agents"""
    template_name = 'delivery/manual_assignment_simple.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        
        try:
            # Fix: Use order_id (UUID) instead of order_number
            order = get_object_or_404(Order, order_id=order_id)
            print(f"DEBUG: Found order {order.order_number} with status {order.status}")
            
            # Get the store for the current user
            try:
                store = Store.objects.get(owner=self.request.user)
                print(f"DEBUG: User {self.request.user.email} owns store {store.name}")
            except Store.DoesNotExist:
                store = Store.objects.filter(staff=self.request.user).first()
                if not store:
                    print(f"DEBUG: No store found for user {self.request.user.email}")
                    messages.error(self.request, 'Store not found for your account.')
                    return context
                print(f"DEBUG: User {self.request.user.email} is staff at store {store.name}")
            
            # Verify the order belongs to this store
            if order.store != store:
                print(f"DEBUG: Order store {order.store.name} != user store {store.name}")
                messages.error(self.request, 'You can only assign agents to your store orders.')
                return context
            
            # Get available agents for this store
            available_agents = DeliveryAgent.objects.filter(
                store=store,  # Filter by the user's store
                is_available=True,
                status='active'
            )
            
            context.update({
                'order': order,
                'available_agents': available_agents,
            })
            
        except Exception as e:
            messages.error(self.request, f"Error loading assignment page: {str(e)}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('order_id')
        agent_id = request.POST.get('agent_id')
        
        try:
            # Fix: Use order_id (UUID) instead of order_number
            order = get_object_or_404(Order, order_id=order_id)
            print(f"DEBUG POST: Processing assignment for order {order.order_number}")
            
            # Verify store ownership
            try:
                store = Store.objects.get(owner=request.user)
            except Store.DoesNotExist:
                store = Store.objects.filter(staff=request.user).first()
                if not store:
                    messages.error(request, 'Store not found for your account.')
                    return redirect('stores:dashboard')
            
            if order.store != store:
                messages.error(request, 'You can only assign agents to your store orders.')
                return redirect('stores:dashboard')
            
            # Get the agent
            agent = get_object_or_404(DeliveryAgent, id=agent_id, store=store)
            
            # Delete existing assignment if any
            from delivery.models import DeliveryAssignment
            DeliveryAssignment.objects.filter(order=order).delete()
            
            # Manually assign the order
            assignment = DeliveryAssignmentService.assign_order_to_agent(
                order=order,
                manual_agent_id=agent.id
            )
            
            if assignment:
                # Update order status to out_for_delivery when agent is assigned
                order.status = 'out_for_delivery'
                order.save()
                
                # Update assignment status to accepted (ready for pickup)
                assignment.status = 'accepted'
                assignment.save()
                
                messages.success(request, f"✅ Order successfully assigned to {agent.user.get_full_name()} - Order is now Out for Delivery")
                
                # Redirect back to store dashboard instead of order detail
                return redirect('stores:dashboard')
            else:
                messages.error(request, "❌ Failed to assign order. Please try again.")
                
        except Exception as e:
            messages.error(request, f"❌ Error assigning order: {str(e)}")
        
        # If we get here, something went wrong - redirect back to assignment page
        return redirect('delivery:manual_assignment', order_id=order_id)


class TestAssignmentView(View):
    """Test view without any authentication to debug the issue"""
    def get(self, request, order_id):
        print(f"DEBUG: Test view - User {request.user} trying to access")
        print(f"DEBUG: User authenticated: {request.user.is_authenticated}")
        print(f"DEBUG: User type: {getattr(request.user, 'user_type', 'No user_type')}")
        
        try:
            order = get_object_or_404(Order, order_id=order_id)
            print(f"DEBUG: Order found: {order.order_id} - Status: {order.status}")
            
            # Get available agents
            available_agents = DeliveryAgent.objects.filter(status='active')
            print(f"DEBUG: Found {available_agents.count()} available agents")
            
            context = {
                'order': order,
                'agents': available_agents,
            }
            return render(request, 'stores/delivery/test_assignment.html', context)
                
        except Exception as e:
            print(f"DEBUG: Exception in TestAssignmentView: {str(e)}")
            return HttpResponse(f"Error: {str(e)}")
