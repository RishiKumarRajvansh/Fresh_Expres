"""
Views for Loyalty and Rewards System
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
import string
import random
from .models import (
    UserLoyaltyAccount, LoyaltyReward, 
    LoyaltyProgram, UserRewardRedemption, ReferralProgram,
    LoyaltyConfiguration
)

@login_required
def loyalty_dashboard(request):
    """User's loyalty dashboard showing points, tier, and available rewards"""
    try:
        loyalty_account = UserLoyaltyAccount.objects.get(user=request.user)
    except UserLoyaltyAccount.DoesNotExist:
        # Create account if doesn't exist
        loyalty_account = UserLoyaltyAccount.objects.create(user=request.user)
    
    # Get loyalty configuration
    config = LoyaltyConfiguration.get_active_config()
    
    # Get tier progression information
    next_tier, next_tier_points, progress_percent = loyalty_account.get_next_tier_info()
    
    # Get recent transactions
    recent_transactions = loyalty_account.transactions.all()[:10]
    
    # Get available rewards
    available_rewards = LoyaltyReward.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_until__gte=timezone.now(),
        points_required__lte=loyalty_account.available_points
    )
    
    # Get user's redeemed rewards
    redeemed_rewards = UserRewardRedemption.objects.filter(user=request.user)[:5]
    
    # Calculate tier thresholds for progress display
    tier_thresholds = {
        'Bronze': config.bronze_threshold if config else 0,
        'Silver': config.silver_threshold if config else 1000,
        'Gold': config.gold_threshold if config else 2000,
        'Platinum': config.platinum_threshold if config else 3000,
    }

    context = {
        'loyalty_account': loyalty_account,
        'recent_transactions': recent_transactions,
        'available_rewards': available_rewards,
        'redeemed_rewards': redeemed_rewards,
        'next_tier': next_tier,
        'next_tier_points': max(0, next_tier_points),
        'tier_thresholds': tier_thresholds,
        'progress_percent': round(progress_percent, 1),
        'config': config,
    }
    
    return render(request, 'accounts/loyalty_dashboard.html', context)

@login_required
@require_POST
def redeem_reward(request, reward_id):
    """Redeem a loyalty reward"""
    try:
        with transaction.atomic():
            reward = get_object_or_404(LoyaltyReward, id=reward_id)
            loyalty_account = UserLoyaltyAccount.objects.select_for_update().get(user=request.user)
            
            # Check if reward is available
            if not reward.is_available:
                return JsonResponse({
                    'success': False,
                    'message': 'This reward is no longer available.'
                })
            
            # Check if user has enough points
            if loyalty_account.available_points < reward.points_required:
                return JsonResponse({
                    'success': False,
                    'message': 'You don\'t have enough points for this reward.'
                })
            
            # Check redemption limits
            user_redemptions = UserRewardRedemption.objects.filter(
                user=request.user,
                reward=reward
            ).count()
            
            if user_redemptions >= reward.max_redemptions_per_user:
                return JsonResponse({
                    'success': False,
                    'message': 'You have already redeemed this reward the maximum number of times.'
                })
            
            # Generate unique coupon code
            coupon_code = generate_coupon_code()
            
            # Create redemption record
            redemption = UserRewardRedemption.objects.create(
                user=request.user,
                reward=reward,
                points_used=reward.points_required,
                coupon_code=coupon_code
            )
            
            # Deduct points
            loyalty_account.redeem_points(
                reward.points_required,
                f"Redeemed: {reward.title}"
            )
            
            # Update reward redemption count
            reward.current_redemptions += 1
            reward.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully redeemed {reward.title}!',
                'coupon_code': coupon_code,
                'remaining_points': loyalty_account.available_points
            })
            
    except UserLoyaltyAccount.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Loyalty account not found.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })

@login_required
def referral_program(request):
    """Referral program page"""
    try:
        loyalty_account = UserLoyaltyAccount.objects.get(user=request.user)
    except UserLoyaltyAccount.DoesNotExist:
        return redirect('accounts:profile')
    
    # Get user's referrals
    referrals_made = ReferralProgram.objects.filter(referrer=request.user)
    
    # Generate referral link
    referral_code = generate_referral_code(request.user.id)
    referral_link = request.build_absolute_uri(f'/auth/register/?ref={referral_code}')
    
    # Get referral stats
    total_referrals = referrals_made.count()
    successful_referrals = referrals_made.filter(referrer_bonus_given=True).count()
    
    context = {
        'loyalty_account': loyalty_account,
        'referrals_made': referrals_made,
        'referral_link': referral_link,
        'referral_code': referral_code,
        'total_referrals': total_referrals,
        'successful_referrals': successful_referrals,
    }
    
    return render(request, 'accounts/referral_program.html', context)

def generate_coupon_code():
    """Generate a unique coupon code"""
    return 'LP' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_referral_code(user_id):
    """Generate referral code based on user ID"""
    return f"REF{user_id:06d}"

@login_required
def transaction_history(request):
    """Show loyalty transaction history"""
    try:
        loyalty_account = UserLoyaltyAccount.objects.get(user=request.user)
        transactions = loyalty_account.transactions.all()
    except UserLoyaltyAccount.DoesNotExist:
        transactions = []
        loyalty_account = None
    
    context = {
        'loyalty_account': loyalty_account,
        'transactions': transactions
    }
    
    return render(request, 'accounts/transaction_history.html', context)
