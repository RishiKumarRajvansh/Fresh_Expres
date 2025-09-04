"""
Push Notification Service for Real-time Customer Engagement
Handles sending web push notifications with advanced targeting and analytics
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from django.conf import settings
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

# Import pywebpush only if available
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    WebPushException = Exception  # Fallback

from core.models_notifications import (
    PushSubscription, NotificationTemplate, NotificationCampaign,
    NotificationLog, NotificationPreference
)

User = get_user_model()
logger = logging.getLogger(__name__)


class PushNotificationService:
    """Core service for sending push notifications"""
    
    def __init__(self):
        self.vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        self.vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)
        self.vapid_claims = getattr(settings, 'VAPID_CLAIMS', {
            'sub': 'mailto:admin@freshmeat.com'
        })
        
        if not all([self.vapid_private_key, self.vapid_public_key]):
            logger.warning("VAPID keys not configured. Push notifications will not work.")
    
    def send_notification_to_user(
        self,
        user: User,
        notification_type: str,
        context: Dict = None,
        template_id: Optional[int] = None
    ) -> Dict:
        """Send notification to a specific user"""
        if context is None:
            context = {}
        
        try:
            # Get user preferences
            preferences = self.get_user_preferences(user)
            if not preferences.can_send_notification(notification_type):
                return {
                    'success': False,
                    'error': 'User has disabled this type of notification',
                    'sent_count': 0
                }
            
            # Get active subscriptions
            subscriptions = PushSubscription.objects.filter(
                user=user,
                is_active=True
            )
            
            if not subscriptions.exists():
                return {
                    'success': False,
                    'error': 'No active push subscriptions found',
                    'sent_count': 0
                }
            
            # Get notification template
            if template_id:
                template = NotificationTemplate.objects.get(id=template_id)
            else:
                template = NotificationTemplate.objects.get(
                    notification_type=notification_type,
                    is_active=True
                )
            
            # Render notification content
            notification_data = template.render_notification(context)
            
            # Send to all user subscriptions
            results = []
            for subscription in subscriptions:
                result = self._send_to_subscription(
                    subscription=subscription,
                    template=template,
                    notification_data=notification_data,
                    user=user
                )
                results.append(result)
            
            successful_sends = sum(1 for r in results if r['success'])
            
            return {
                'success': successful_sends > 0,
                'sent_count': successful_sends,
                'total_subscriptions': len(results),
                'results': results
            }
        
        except NotificationTemplate.DoesNotExist:
            logger.error(f"Notification template not found for type: {notification_type}")
            return {
                'success': False,
                'error': 'Notification template not found',
                'sent_count': 0
            }
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0
            }
    
    def send_bulk_notification(
        self,
        users: List[User],
        notification_type: str,
        context: Dict = None,
        template_id: Optional[int] = None
    ) -> Dict:
        """Send notifications to multiple users"""
        if context is None:
            context = {}
        
        total_sent = 0
        total_failed = 0
        results = []
        
        for user in users:
            result = self.send_notification_to_user(
                user=user,
                notification_type=notification_type,
                context=context,
                template_id=template_id
            )
            
            if result['success']:
                total_sent += result['sent_count']
            else:
                total_failed += 1
            
            results.append({
                'user_id': user.id,
                'username': user.username,
                **result
            })
        
        return {
            'success': total_sent > 0,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'total_users': len(users),
            'results': results
        }
    
    def send_campaign_notification(self, campaign_id: int) -> Dict:
        """Send notifications for a campaign"""
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            
            # Check if campaign is ready to send
            if campaign.status not in ['scheduled', 'draft']:
                return {
                    'success': False,
                    'error': f'Campaign status is {campaign.status}, cannot send'
                }
            
            # Get target users
            target_users = self._get_campaign_target_users(campaign)
            
            # Update campaign status
            campaign.status = 'running'
            campaign.started_at = timezone.now()
            campaign.target_count = len(target_users)
            campaign.save()
            
            # Send notifications
            results = []
            successful_sends = 0
            
            for user in target_users:
                try:
                    # Get user preferences
                    preferences = self.get_user_preferences(user)
                    if not preferences.can_send_notification(campaign.template.notification_type):
                        continue
                    
                    # Get active subscriptions
                    subscriptions = PushSubscription.objects.filter(
                        user=user,
                        is_active=True
                    )
                    
                    for subscription in subscriptions:
                        # Render notification with campaign context
                        context = campaign.targeting_criteria.get('context', {})
                        notification_data = campaign.template.render_notification(context)
                        
                        result = self._send_to_subscription(
                            subscription=subscription,
                            template=campaign.template,
                            notification_data=notification_data,
                            user=user,
                            campaign=campaign
                        )
                        
                        if result['success']:
                            successful_sends += 1
                        
                        results.append(result)
                
                except Exception as e:
                    logger.error(f"Failed to send campaign notification to user {user.id}: {str(e)}")
            
            # Update campaign results
            campaign.sent_count = successful_sends
            campaign.status = 'completed'
            campaign.completed_at = timezone.now()
            campaign.save()
            
            return {
                'success': successful_sends > 0,
                'campaign_id': campaign.id,
                'sent_count': successful_sends,
                'target_count': campaign.target_count,
                'results': results
            }
        
        except NotificationCampaign.DoesNotExist:
            return {
                'success': False,
                'error': 'Campaign not found'
            }
        except Exception as e:
            logger.error(f"Campaign send failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_to_subscription(
        self,
        subscription: PushSubscription,
        template: NotificationTemplate,
        notification_data: Dict,
        user: User,
        campaign: Optional[NotificationCampaign] = None
    ) -> Dict:
        """Send notification to a specific subscription"""
        # Create log entry
        log_entry = NotificationLog.objects.create(
            user=user,
            subscription=subscription,
            campaign=campaign,
            template=template,
            title=notification_data['title'],
            body=notification_data['body'],
            notification_data=notification_data,
            status='pending'
        )
        
        try:
            # Prepare push data
            push_data = json.dumps(notification_data)
            
            # Send push notification
            response = webpush(
                subscription_info=subscription.to_subscription_info(),
                data=push_data,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            
            # Update log entry
            log_entry.status = 'sent'
            log_entry.sent_at = timezone.now()
            log_entry.save()
            
            logger.info(f"Push notification sent successfully to {user.username}")
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'log_id': log_entry.id,
                'response_status': response.status_code
            }
        
        except WebPushException as e:
            # Handle specific web push errors
            error_msg = str(e)
            
            # Deactivate subscription if endpoint is invalid
            if e.response and e.response.status_code in [400, 404, 410, 413]:
                subscription.is_active = False
                subscription.save()
                error_msg += " (Subscription deactivated)"
            
            # Update log entry
            log_entry.status = 'failed'
            log_entry.error_message = error_msg
            log_entry.save()
            
            logger.error(f"WebPush error for {user.username}: {error_msg}")
            
            return {
                'success': False,
                'subscription_id': subscription.id,
                'log_id': log_entry.id,
                'error': error_msg
            }
        
        except Exception as e:
            error_msg = str(e)
            
            # Update log entry
            log_entry.status = 'failed'
            log_entry.error_message = error_msg
            log_entry.save()
            
            logger.error(f"Push notification failed for {user.username}: {error_msg}")
            
            return {
                'success': False,
                'subscription_id': subscription.id,
                'log_id': log_entry.id,
                'error': error_msg
            }
    
    def _get_campaign_target_users(self, campaign: NotificationCampaign) -> List[User]:
        """Get target users for a campaign based on targeting criteria"""
        targeting_type = campaign.targeting_type
        criteria = campaign.targeting_criteria
        
        # Base queryset - only users with active push subscriptions
        base_queryset = User.objects.filter(
            push_subscriptions__is_active=True,
            is_active=True
        ).distinct()
        
        if targeting_type == 'all_users':
            return list(base_queryset)
        
        elif targeting_type == 'active_users':
            cutoff_date = timezone.now() - timedelta(days=30)
            return list(base_queryset.filter(last_login__gte=cutoff_date))
        
        elif targeting_type == 'new_users':
            cutoff_date = timezone.now() - timedelta(days=7)
            return list(base_queryset.filter(date_joined__gte=cutoff_date))
        
        elif targeting_type == 'location_based':
            zip_codes = criteria.get('zip_codes', [])
            if zip_codes:
                return list(base_queryset.filter(
                    profile__zip_code__in=zip_codes
                ))
        
        elif targeting_type == 'purchase_history':
            # Users who purchased specific categories or products
            category_ids = criteria.get('category_ids', [])
            product_ids = criteria.get('product_ids', [])
            days_back = criteria.get('days_back', 30)
            
            cutoff_date = timezone.now() - timedelta(days=days_back)
            queryset = base_queryset.filter(
                orders__created_at__gte=cutoff_date
            )
            
            if category_ids:
                queryset = queryset.filter(
                    orders__orderitem__product__category__id__in=category_ids
                )
            
            if product_ids:
                queryset = queryset.filter(
                    orders__orderitem__product__id__in=product_ids
                )
            
            return list(queryset.distinct())
        
        elif targeting_type == 'loyalty_tier':
            tier_levels = criteria.get('tier_levels', [])
            if tier_levels:
                return list(base_queryset.filter(
                    loyaltymember__tier__level__in=tier_levels
                ))
        
        elif targeting_type == 'custom_segment':
            # Custom SQL or complex filtering
            user_ids = criteria.get('user_ids', [])
            if user_ids:
                return list(base_queryset.filter(id__in=user_ids))
        
        return []
    
    def get_user_preferences(self, user: User) -> NotificationPreference:
        """Get or create notification preferences for user"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user,
            defaults={
                'push_notifications_enabled': True,
                'order_notifications': True,
                'delivery_notifications': True,
                'promotional_notifications': False,
                'stock_notifications': False,
                'store_notifications': True,
                'loyalty_notifications': True,
            }
        )
        return preferences
    
    def track_notification_click(self, log_id: int) -> bool:
        """Track when a notification is clicked"""
        try:
            log_entry = NotificationLog.objects.get(id=log_id)
            if log_entry.status in ['sent', 'delivered']:
                log_entry.status = 'clicked'
                log_entry.clicked_at = timezone.now()
                log_entry.save()
                
                # Update campaign statistics
                if log_entry.campaign:
                    NotificationCampaign.objects.filter(
                        id=log_entry.campaign.id
                    ).update(
                        clicked_count=Count('notificationlog__id', filter=Q(
                            notificationlog__status='clicked'
                        ))
                    )
                
                return True
        except NotificationLog.DoesNotExist:
            logger.error(f"Notification log {log_id} not found")
        except Exception as e:
            logger.error(f"Failed to track notification click: {str(e)}")
        
        return False
    
    def get_campaign_analytics(self, campaign_id: int) -> Dict:
        """Get detailed analytics for a campaign"""
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            
            # Get log entries for this campaign
            logs = NotificationLog.objects.filter(campaign=campaign)
            
            analytics = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'status': campaign.status,
                'target_count': campaign.target_count,
                'sent_count': logs.filter(status__in=['sent', 'delivered', 'clicked']).count(),
                'delivered_count': logs.filter(status__in=['delivered', 'clicked']).count(),
                'clicked_count': logs.filter(status='clicked').count(),
                'failed_count': logs.filter(status='failed').count(),
                'delivery_rate': 0,
                'click_rate': 0,
                'started_at': campaign.started_at,
                'completed_at': campaign.completed_at,
            }
            
            # Calculate rates
            if analytics['sent_count'] > 0:
                analytics['delivery_rate'] = (analytics['delivered_count'] / analytics['sent_count']) * 100
            
            if analytics['delivered_count'] > 0:
                analytics['click_rate'] = (analytics['clicked_count'] / analytics['delivered_count']) * 100
            
            # Get hourly breakdown
            if campaign.started_at and campaign.completed_at:
                hourly_stats = self._get_hourly_campaign_stats(campaign)
                analytics['hourly_breakdown'] = hourly_stats
            
            return analytics
        
        except NotificationCampaign.DoesNotExist:
            return {'error': 'Campaign not found'}
        except Exception as e:
            logger.error(f"Failed to get campaign analytics: {str(e)}")
            return {'error': str(e)}
    
    def _get_hourly_campaign_stats(self, campaign: NotificationCampaign) -> List[Dict]:
        """Get hourly statistics for a campaign"""
        from django.db.models import Count
        from django.db.models.functions import TruncHour
        
        stats = NotificationLog.objects.filter(
            campaign=campaign,
            sent_at__isnull=False
        ).annotate(
            hour=TruncHour('sent_at')
        ).values('hour').annotate(
            sent=Count('id'),
            delivered=Count('id', filter=Q(status__in=['delivered', 'clicked'])),
            clicked=Count('id', filter=Q(status='clicked'))
        ).order_by('hour')
        
        return list(stats)


# Convenience functions for common notification scenarios
def send_order_notification(order, notification_type: str, context: Dict = None):
    """Send order-related notification"""
    service = PushNotificationService()
    
    if context is None:
        context = {}
    
    # Add order-specific context
    context.update({
        'order_id': order.id,
        'order_number': order.order_number,
        'store_name': order.store.name,
        'total_amount': str(order.total_amount),
        'url': f'/orders/track/{order.id}/',
    })
    
    return service.send_notification_to_user(
        user=order.user,
        notification_type=notification_type,
        context=context
    )


def send_delivery_notification(delivery, notification_type: str, context: Dict = None):
    """Send delivery-related notification"""
    service = PushNotificationService()
    
    if context is None:
        context = {}
    
    # Add delivery-specific context
    context.update({
        'delivery_id': delivery.id,
        'order_id': delivery.order.id,
        'agent_name': delivery.delivery_agent.user.get_full_name(),
        'estimated_time': delivery.estimated_delivery_time.strftime('%H:%M') if delivery.estimated_delivery_time else '',
        'url': f'/delivery/track/{delivery.id}/',
    })
    
    return service.send_notification_to_user(
        user=delivery.order.user,
        notification_type=notification_type,
        context=context
    )


def send_stock_notification(product, store, users: List[User], notification_type: str):
    """Send stock-related notifications to multiple users"""
    service = PushNotificationService()
    
    context = {
        'product_name': product.name,
        'store_name': store.name,
        'product_id': product.id,
        'url': f'/catalog/product/{product.id}/',
    }
    
    return service.send_bulk_notification(
        users=users,
        notification_type=notification_type,
        context=context
    )
