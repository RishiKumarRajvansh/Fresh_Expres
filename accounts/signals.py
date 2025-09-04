"""
Signals for automatic loyalty points processing
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from orders.models import Order
from .models import UserLoyaltyAccount, LoyaltyProgram, ReferralProgram, LoyaltyConfiguration

User = get_user_model()

@receiver(post_save, sender=Order)
def award_loyalty_points(sender, instance, created, **kwargs):
    """Award loyalty points when order is delivered"""
    if instance.status == 'delivered' and not hasattr(instance, '_loyalty_points_awarded'):
        # Get or create user loyalty account
        loyalty_account, created = UserLoyaltyAccount.objects.get_or_create(
            user=instance.user
        )
        
        # Calculate points based on dynamic configuration
        points_to_award = loyalty_account.calculate_points_for_order(instance.total_amount)
        
        if points_to_award > 0:
            # Award points
            loyalty_account.add_points(
                points_to_award,
                f"Order #{instance.order_number} - ₹{instance.total_amount}"
            )
        
        # Mark as processed to avoid duplicate awards
        instance._loyalty_points_awarded = True

@receiver(post_save, sender=Order)
def process_referral_bonus(sender, instance, created, **kwargs):
    """Process referral bonus when referred user makes their first order"""
    if instance.status == 'delivered':
        # Check if this is user's first delivered order
        user_delivered_orders = Order.objects.filter(
            user=instance.user,
            status='delivered'
        ).count()
        
        if user_delivered_orders == 1:  # This is the first delivered order
            # Check if user was referred
            try:
                referral = ReferralProgram.objects.get(referred=instance.user)
                if not referral.referred_first_order:
                    referral.referred_first_order = instance
                    referral.save()
                    
                    # Process referral bonus for both users
                    if not referral.referrer_bonus_given:
                        try:
                            # Award bonus to referrer
                            referrer_loyalty = UserLoyaltyAccount.objects.get(user=referral.referrer)
                            referrer_loyalty.add_points(
                                points=100,
                                transaction_type='referral_bonus',
                                reason=f'Referral bonus for inviting {instance.user.get_full_name() or instance.user.username}'
                            )
                            referral.referrer_bonus_given = True
                        except UserLoyaltyAccount.DoesNotExist:
                            pass
                    
                    if not referral.referred_bonus_given:
                        try:
                            # Award bonus to referred user
                            referred_loyalty = UserLoyaltyAccount.objects.get(user=instance.user)
                            referred_loyalty.add_points(
                                points=100,
                                transaction_type='referral_order_bonus',
                                reason='Bonus for completing first order through referral'
                            )
                            referral.referred_bonus_given = True
                        except UserLoyaltyAccount.DoesNotExist:
                            pass
                    
                    referral.bonus_awarded_at = timezone.now()
                    referral.save()
                    
            except ReferralProgram.DoesNotExist:
                pass  # User wasn't referred

@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    """Create loyalty account for new customer users"""
    if created and instance.user_type == 'customer':
        UserLoyaltyAccount.objects.get_or_create(user=instance)
        
        # Give signup bonus
        config = LoyaltyConfiguration.get_active_config()
        if config and config.signup_bonus_points > 0:
            try:
                loyalty_account = UserLoyaltyAccount.objects.get(user=instance)
                loyalty_account.add_points(
                    config.signup_bonus_points,
                    'Welcome bonus for joining Fresh Express'
                )
            except UserLoyaltyAccount.DoesNotExist:
                pass
