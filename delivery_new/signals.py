from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import models
from .models import Delivery, DeliveryTracking, DeliveryRating
from django.utils import timezone
from decimal import Decimal


@receiver(post_save, sender=Delivery)
def update_tracking_on_status_change(sender, instance, created, **kwargs):
    """Create a tracking entry when delivery status changes"""
    if created:
        # Create initial tracking point for new delivery
        DeliveryTracking.objects.create(
            delivery=instance,
            latitude=instance.agent.current_latitude or Decimal('0.0'),
            longitude=instance.agent.current_longitude or Decimal('0.0')
        )
    else:
        # Get the latest tracking point
        latest_tracking = DeliveryTracking.objects.filter(delivery=instance).order_by('-timestamp').first()
        
        # Only create a new tracking point if status has changed from previous state
        if latest_tracking and instance.agent.current_latitude and instance.agent.current_longitude:
            # Create new tracking point for location change
            DeliveryTracking.objects.create(
                delivery=instance,
                latitude=instance.agent.current_latitude,
                longitude=instance.agent.current_longitude
            )


@receiver(post_save, sender=Delivery)
def update_agent_stats_on_delivery_completion(sender, instance, created, **kwargs):
    """Update agent statistics when a delivery is completed or failed"""
    if not created and instance.agent:
        agent = instance.agent
        
        # Only proceed if we have a status change that matters for stats
        if instance.status in ['delivered', 'failed', 'cancelled']:
            # Get all agent's deliveries
            agent_deliveries = Delivery.objects.filter(agent=agent)
            
            # Count totals
            total_deliveries = agent_deliveries.count()
            successful_deliveries = agent_deliveries.filter(status='delivered').count()
            failed_deliveries = agent_deliveries.filter(status__in=['failed', 'cancelled']).count()
            
            # Calculate earnings (only from successful deliveries)
            total_earnings = agent_deliveries.filter(status='delivered').aggregate(
                total=models.Sum('agent_payout')
            )['total'] or Decimal('0.00')
            
            # Update agent stats
            agent.total_deliveries = total_deliveries
            agent.successful_deliveries = successful_deliveries
            agent.failed_deliveries = failed_deliveries
            agent.total_earnings = total_earnings
            agent.save()


@receiver(post_save, sender=DeliveryRating)
def update_agent_rating(sender, instance, created, **kwargs):
    """Update agent's average rating when a new rating is submitted"""
    if created and instance.delivery and instance.delivery.agent:
        agent = instance.delivery.agent
        
        # Get all ratings for this agent
        agent_ratings = DeliveryRating.objects.filter(
            delivery__agent=agent
        )
        
        # Calculate new average
        total_rating = sum(rating.rating for rating in agent_ratings)
        count = agent_ratings.count()
        
        if count > 0:
            agent.average_rating = Decimal(total_rating) / Decimal(count)
            agent.save()
