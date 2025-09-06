from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, View, TemplateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from .models import DeliveryAgent, Delivery, DeliveryTracking, DeliveryIssue, DeliveryRating
from orders.models import Order
from .forms import DeliveryOTPForm, DeliveryIssueForm, DeliveryRatingForm, DeliveryAgentZipCoverageForm

from decimal import Decimal
import json
import datetime

# Custom mixins
class DeliveryAgentRequiredMixin(LoginRequiredMixin):
    """Ensure the user is a delivery agent"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.user_type != 'delivery_agent':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('core:home')
            
        # Check if user has a DeliveryAgent profile
        try:
            self.agent = DeliveryAgent.objects.get(user=request.user)
        except DeliveryAgent.DoesNotExist:
            messages.error(request, "You need a delivery agent profile to access this page.")
            return redirect('core:home')
            
        return super().dispatch(request, *args, **kwargs)


# Dashboard Views
class AgentDashboardView(DeliveryAgentRequiredMixin, TemplateView):
    """Dashboard for delivery agents"""
    template_name = 'delivery_new/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.agent
        
        # Today's date for filtering
        today = timezone.now().date()
        
        # Current deliveries
        active_deliveries = Delivery.objects.filter(
            agent=agent,
            status__in=['assigned', 'accepted', 'at_store', 'picked_up', 'in_transit']
        ).select_related('order', 'order__user')
        
        # Get counts by status
        status_counts = {
            'assigned': active_deliveries.filter(status='assigned').count(),
            'accepted': active_deliveries.filter(status='accepted').count(),
            'at_store': active_deliveries.filter(status='at_store').count(),
            'picked_up': active_deliveries.filter(status='picked_up').count(),
            'in_transit': active_deliveries.filter(status='in_transit').count(),
            'all_active': active_deliveries.count(),
        }
        
        # Today's statistics
        today_deliveries = Delivery.objects.filter(
            agent=agent,
            created_at__date=today
        )
        
        completed_today = today_deliveries.filter(status='delivered')
        
        today_earnings = completed_today.aggregate(
            total=Sum('agent_payout')
        )['total'] or Decimal('0.00')
        
        # All time statistics
        all_completed = Delivery.objects.filter(agent=agent, status='delivered')
        all_time_earnings = all_completed.aggregate(
            total=Sum('agent_payout')
        )['total'] or Decimal('0.00')
        
        # Calculate completion rate
        if agent.total_deliveries > 0:
            completion_rate = (agent.successful_deliveries / agent.total_deliveries) * 100
        else:
            completion_rate = 0
        
        context.update({
            'agent': agent,
            'active_deliveries': active_deliveries,
            'status_counts': status_counts,
            'today_stats': {
                'deliveries': today_deliveries.count(),
                'completed': completed_today.count(),
                'earnings': today_earnings,
            },
            'all_time_stats': {
                'total_deliveries': agent.total_deliveries,
                'completed': agent.successful_deliveries,
                'earnings': all_time_earnings,
                'completion_rate': completion_rate,
                'average_rating': agent.average_rating,
            }
        })
        
        return context


class DeliveryListView(DeliveryAgentRequiredMixin, ListView):
    """List of deliveries for an agent"""
    model = Delivery
    template_name = 'delivery_new/delivery_list.html'
    context_object_name = 'deliveries'
    paginate_by = 20
    
    def get_queryset(self):
        agent = self.agent
        status_filter = self.request.GET.get('status', 'active')
        
        # Base queryset
        queryset = Delivery.objects.filter(agent=agent)
        
        # Apply status filtering
        if status_filter == 'active':
            queryset = queryset.filter(status__in=['assigned', 'accepted', 'at_store', 'picked_up', 'in_transit'])
        elif status_filter == 'pending':
            queryset = queryset.filter(status='assigned')
        elif status_filter == 'in_progress':
            queryset = queryset.filter(status__in=['accepted', 'at_store', 'picked_up', 'in_transit'])
        elif status_filter == 'completed':
            queryset = queryset.filter(status='delivered')
        elif status_filter == 'problematic':
            queryset = queryset.filter(status__in=['cancelled', 'failed'])
        
        # Apply date filtering if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from)
            except ValueError:
                pass
                
        if date_to:
            try:
                date_to = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to)
            except ValueError:
                pass
        
        # Order by most recent first
        return queryset.select_related('order', 'order__user', 'order__store').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.agent
        
        # Get counts for each status
        context['status_counts'] = {
            'active': Delivery.objects.filter(
                agent=agent, 
                status__in=['assigned', 'accepted', 'at_store', 'picked_up', 'in_transit']
            ).count(),
            'pending': Delivery.objects.filter(agent=agent, status='assigned').count(),
            'in_progress': Delivery.objects.filter(
                agent=agent,
                status__in=['accepted', 'at_store', 'picked_up', 'in_transit']
            ).count(),
            'completed': Delivery.objects.filter(agent=agent, status='delivered').count(),
            'problematic': Delivery.objects.filter(agent=agent, status__in=['cancelled', 'failed']).count(),
            'all': Delivery.objects.filter(agent=agent).count(),
        }
        
        # Current status filter
        context['current_status'] = self.request.GET.get('status', 'active')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        return context


class DeliveryDetailView(DeliveryAgentRequiredMixin, DetailView):
    """Detail view for a single delivery"""
    model = Delivery
    template_name = 'delivery_new/delivery_detail.html'
    context_object_name = 'delivery'
    
    def get_queryset(self):
        # Ensure agent can only view their own deliveries
        return Delivery.objects.filter(
            agent=self.agent
        ).select_related('order', 'order__user', 'order__store')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        delivery = self.get_object()
        
        # Add order items
        context['order_items'] = delivery.order.items.all().select_related('store_product')
        
        # Add tracking history
        context['tracking_history'] = delivery.tracking_points.all()[:10]
        
        # Add any issues
        context['issues'] = delivery.issues.all()
        
        # Add OTP form if applicable
        current_status = delivery.status
        if current_status in ['at_store', 'picked_up', 'in_transit']:
            context['otp_form'] = DeliveryOTPForm()
            
            # Determine which verification we're doing
            if current_status == 'at_store':
                context['verification_type'] = 'store_pickup'
                context['otp_action'] = reverse('delivery:verify_store_pickup', args=[delivery.pk])
            elif current_status in ['picked_up', 'in_transit']:
                context['verification_type'] = 'customer_delivery'
                context['otp_action'] = reverse('delivery:verify_customer_delivery', args=[delivery.pk])
        
        return context


# Action Views
class AcceptDeliveryView(DeliveryAgentRequiredMixin, View):
    """Accept a delivery assignment"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent, status='assigned')
        
        if delivery.accept_delivery():
            messages.success(request, f"You've accepted delivery {delivery.delivery_id}")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)
        else:
            messages.error(request, "Unable to accept this delivery. It may have already been accepted or cancelled.")
            return redirect('delivery_new:delivery_list')


class ArriveAtStoreView(DeliveryAgentRequiredMixin, View):
    """Mark arrival at store"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent, status='accepted')
        
        if delivery.arrive_at_store():
            messages.success(request, f"You've marked your arrival at the store.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)
        else:
            messages.error(request, "Unable to update status. Please make sure you've accepted this delivery.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)


class VerifyStorePickupView(DeliveryAgentRequiredMixin, View):
    """Verify store pickup with OTP"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent, status='at_store')
        form = DeliveryOTPForm(request.POST)
        
        if form.is_valid():
            otp = form.cleaned_data['otp']
            if delivery.pickup_from_store(otp):
                messages.success(request, "Store pickup verified! You can now proceed with the delivery.")
                return redirect('delivery_new:delivery_detail', pk=delivery.pk)
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        else:
            messages.error(request, "Invalid form submission.")
            
        return redirect('delivery_new:delivery_detail', pk=delivery.pk)


class StartTransitView(DeliveryAgentRequiredMixin, View):
    """Mark delivery as in transit"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent, status='picked_up')
        
        if delivery.mark_in_transit():
            messages.success(request, "Delivery marked as in transit to customer.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)
        else:
            messages.error(request, "Unable to update status.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)


class VerifyCustomerDeliveryView(DeliveryAgentRequiredMixin, View):
    """Verify customer delivery with OTP"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(
            Delivery, 
            pk=pk, 
            agent=self.agent,
            status__in=['picked_up', 'in_transit']
        )
        form = DeliveryOTPForm(request.POST)
        
        if form.is_valid():
            otp = form.cleaned_data['otp']
            if delivery.complete_delivery(otp):
                messages.success(request, "Delivery successfully completed! Thank you.")
                return redirect('delivery_new:delivery_list')
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        else:
            messages.error(request, "Invalid form submission.")
            
        return redirect('delivery_new:delivery_detail', pk=delivery.pk)


class ReportDeliveryIssueView(DeliveryAgentRequiredMixin, View):
    """Report an issue with a delivery"""
    
    def get(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent)
        form = DeliveryIssueForm()
        
        return render(request, 'delivery_new/report_issue.html', {
            'delivery': delivery,
            'form': form
        })
    
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, agent=self.agent)
        form = DeliveryIssueForm(request.POST)
        
        if form.is_valid():
            issue = form.save(commit=False)
            issue.delivery = delivery
            issue.save()
            
            messages.success(request, "Issue reported successfully. Our team will look into it.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)
        
        return render(request, 'delivery_new/report_issue.html', {
            'delivery': delivery,
            'form': form
        })


class CancelDeliveryView(DeliveryAgentRequiredMixin, View):
    """Cancel a delivery"""
    
    def post(self, request, pk):
        delivery = get_object_or_404(
            Delivery, 
            pk=pk, 
            agent=self.agent,
            status__in=['assigned', 'accepted', 'at_store']
        )
        
        # Get reason for cancellation
        reason = request.POST.get('reason', '')
        
        if delivery.cancel_delivery():
            # Create an issue record for the cancellation
            DeliveryIssue.objects.create(
                delivery=delivery,
                issue_type='other',
                description=f"Delivery cancelled by agent. Reason: {reason}"
            )
            
            messages.success(request, "Delivery has been cancelled.")
            return redirect('delivery_new:delivery_list')
        else:
            messages.error(request, "Unable to cancel this delivery.")
            return redirect('delivery_new:delivery_detail', pk=delivery.pk)


# Agent Profile and Settings
class AgentProfileView(DeliveryAgentRequiredMixin, DetailView):
    """View agent profile"""
    model = DeliveryAgent
    template_name = 'delivery_new/agent_profile.html'
    context_object_name = 'agent'
    
    def get_object(self):
        return self.agent


class AgentZipCoverageView(DeliveryAgentRequiredMixin, FormView):
    """View for managing agent's ZIP code coverage"""
    template_name = 'delivery_new/agent_zip_coverage.html'
    form_class = DeliveryAgentZipCoverageForm
    success_url = reverse_lazy('delivery_new:agent_profile')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['agent'] = self.agent
        return kwargs
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your service areas have been updated successfully.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agent'] = self.agent
        context['active_zip_areas'] = self.agent.zip_coverages.filter(is_active=True)
        return context


class AgentEarningsView(DeliveryAgentRequiredMixin, TemplateView):
    """View agent earnings"""
    template_name = 'delivery_new/agent_earnings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.agent
        
        # Get date range
        today = timezone.now().date()
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Default to current month
        if not start_date:
            start_date = today.replace(day=1)
        else:
            try:
                start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = today.replace(day=1)
        
        if not end_date:
            end_date = today
        else:
            try:
                end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = today


class RatingsFeedbackView(DeliveryAgentRequiredMixin, TemplateView):
    """View customer ratings and feedback"""
    template_name = 'delivery_new/ratings_feedback.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.agent
        
        # Get ratings from delivery models (assuming DeliveryRating is in delivery app)
        try:
            from delivery.models import DeliveryRating
            
            # Get all ratings for this agent
            ratings = DeliveryRating.objects.filter(
                agent__user=agent.user
            ).select_related('order', 'customer').order_by('-created_at')
            
            # Calculate rating breakdown (percentage for each star level)
            total_ratings = ratings.count()
            breakdown = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            if total_ratings > 0:
                for star in range(1, 6):
                    count = ratings.filter(overall_rating=star).count()
                    breakdown[star] = round((count / total_ratings) * 100)
            
            # Calculate category averages
            category_avg = {
                'delivery_time': ratings.aggregate(avg=Avg('delivery_time_rating'))['avg'] or 0,
                'packaging': ratings.aggregate(avg=Avg('packaging_rating'))['avg'] or 0,
                'agent_behavior': ratings.aggregate(avg=Avg('agent_behavior_rating'))['avg'] or 0,
            }
            
            context.update({
                'agent': agent,
                'ratings': ratings,
                'rating_breakdown': breakdown,
                'category_avg': category_avg,
            })
            
        except ImportError:
            # If the DeliveryRating model isn't available
            context.update({
                'agent': agent,
                'ratings': [],
                'rating_breakdown': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'category_avg': {'delivery_time': 0, 'packaging': 0, 'agent_behavior': 0},
            })
        
        return context
        
        # Get earnings for the date range
        deliveries = Delivery.objects.filter(
            agent=agent,
            status='delivered',
            delivered_at__date__gte=start_date,
            delivered_at__date__lte=end_date
        )
        
        total_earnings = deliveries.aggregate(Sum('agent_payout'))['agent_payout__sum'] or Decimal('0.00')
        
        # Group by day
        daily_earnings = {}
        for delivery in deliveries:
            date = delivery.delivered_at.date()
            if date not in daily_earnings:
                daily_earnings[date] = {
                    'count': 0,
                    'amount': Decimal('0.00')
                }
            
            daily_earnings[date]['count'] += 1
            daily_earnings[date]['amount'] += delivery.agent_payout
        
        # Convert to sorted list
        daily_earnings_list = [
            {
                'date': date,
                'count': data['count'],
                'amount': data['amount']
            }
            for date, data in sorted(daily_earnings.items())
        ]
        
        context.update({
            'agent': agent,
            'start_date': start_date,
            'end_date': end_date,
            'total_earnings': total_earnings,
            'total_deliveries': deliveries.count(),
            'daily_earnings': daily_earnings_list
        })
        
        return context


# API Views for mobile app
@method_decorator(csrf_exempt, name='dispatch')
class ToggleAvailabilityAPIView(View):
    """API to toggle agent availability"""
    
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
        try:
            import json
            # Ensure we're parsing JSON data correctly
            try:
                if request.body:
                    data = json.loads(request.body)
                else:
                    data = {}
            except json.JSONDecodeError:
                data = {}
                
            agent = DeliveryAgent.objects.get(user=request.user)
            
            # Check if agent has ZIP code coverage
            if not agent.zip_coverages.filter(is_active=True).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'ZIP code required. Please set your service areas first.',
                    'redirect_url': None
                }, status=400)
                
            is_available = agent.toggle_availability()
            
            # Ensure we're returning a properly formatted JSON response
            response = JsonResponse({
                'success': True,
                'is_available': is_available,
                'status': agent.status,
                'redirect_url': None  # Don't redirect
            })
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Agent profile not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class UpdateLocationAPIView(View):
    """API to update agent location"""
    
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
        try:
            data = json.loads(request.body)
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            delivery_id = data.get('delivery_id')
            
            if not (latitude and longitude):
                return JsonResponse({'success': False, 'error': 'Latitude and longitude required'}, status=400)
            
            # Update agent location
            agent = DeliveryAgent.objects.get(user=request.user)
            agent.current_latitude = latitude
            agent.current_longitude = longitude
            agent.last_location_update = timezone.now()
            agent.save()
            
            # If delivery_id provided, also add to tracking points
            if delivery_id:
                try:
                    delivery = Delivery.objects.get(delivery_id=delivery_id, agent=agent)
                    DeliveryTracking.objects.create(
                        delivery=delivery,
                        latitude=latitude,
                        longitude=longitude
                    )
                except Delivery.DoesNotExist:
                    pass  # Just update agent location if delivery not found
            
            return JsonResponse({'success': True})
        except DeliveryAgent.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Agent profile not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Customer-facing views
class TrackDeliveryView(DetailView):
    """Allow customers to track their delivery"""
    model = Delivery
    template_name = 'delivery_new/track_delivery.html'
    slug_field = 'delivery_id'
    slug_url_kwarg = 'delivery_id'
    context_object_name = 'delivery'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        delivery = self.get_object()
        
        # Add latest tracking point
        latest_tracking = delivery.tracking_points.order_by('-timestamp').first()
        context['latest_tracking'] = latest_tracking
        
        # Add delivery status steps
        status_steps = [
            {
                'name': 'Assigned',
                'icon': 'task_alt',
                'complete': True,
                'active': delivery.status == 'assigned',
                'timestamp': delivery.assigned_at
            },
            {
                'name': 'Accepted',
                'icon': 'check_circle',
                'complete': delivery.status not in ['assigned'],
                'active': delivery.status == 'accepted',
                'timestamp': delivery.accepted_at
            },
            {
                'name': 'At Store',
                'icon': 'store',
                'complete': delivery.status not in ['assigned', 'accepted'],
                'active': delivery.status == 'at_store',
                'timestamp': delivery.arrived_at_store_at
            },
            {
                'name': 'Picked Up',
                'icon': 'shopping_bag',
                'complete': delivery.status not in ['assigned', 'accepted', 'at_store'],
                'active': delivery.status == 'picked_up',
                'timestamp': delivery.picked_up_at
            },
            {
                'name': 'In Transit',
                'icon': 'local_shipping',
                'complete': delivery.status not in ['assigned', 'accepted', 'at_store', 'picked_up'],
                'active': delivery.status == 'in_transit',
                'timestamp': None
            },
            {
                'name': 'Delivered',
                'icon': 'home',
                'complete': delivery.status == 'delivered',
                'active': delivery.status == 'delivered',
                'timestamp': delivery.delivered_at
            }
        ]
        
        context['status_steps'] = status_steps
        
        # Add rating form if delivered and not yet rated
        if delivery.status == 'delivered' and not hasattr(delivery, 'rating'):
            context['rating_form'] = DeliveryRatingForm()
        
        return context


class SubmitDeliveryRatingView(View):
    """Submit rating for a delivery"""
    
    def post(self, request, delivery_id):
        delivery = get_object_or_404(Delivery, delivery_id=delivery_id, status='delivered')
        
        # Check if already rated
        if hasattr(delivery, 'rating'):
            messages.error(request, "This delivery has already been rated.")
            return redirect('delivery_new:track_delivery', delivery_id=delivery_id)
        
        form = DeliveryRatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.delivery = delivery
            rating.save()
            
            messages.success(request, "Thank you for your feedback!")
        else:
            messages.error(request, "There was an error with your submission. Please try again.")
        
        return redirect('delivery_new:track_delivery', delivery_id=delivery_id)
