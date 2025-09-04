"""
Management command to set up initial loyalty program and sample data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from accounts.models import LoyaltyProgram, LoyaltyReward

class Command(BaseCommand):
    help = 'Set up initial loyalty program and rewards'
    
    def handle(self, *args, **options):
        # Create default loyalty program
        loyalty_program, created = LoyaltyProgram.objects.get_or_create(
            name="Fresh Rewards Program",
            defaults={
                'points_per_rupee': Decimal('1.00'),
                'min_points_to_redeem': 100,
                'redemption_value_per_point': Decimal('0.10'),
                'referral_bonus_points': 100,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created default loyalty program'))
        else:
            self.stdout.write('Loyalty program already exists')
        
        # Create sample rewards
        sample_rewards = [
            {
                'title': '₹50 Off Your Next Order',
                'description': 'Get ₹50 discount on orders above ₹500',
                'reward_type': 'discount',
                'points_required': 500,
                'discount_amount': Decimal('50.00'),
                'max_redemptions_per_user': 5
            },
            {
                'title': 'Free Delivery',
                'description': 'Free delivery on your next order',
                'reward_type': 'free_delivery',
                'points_required': 200,
                'max_redemptions_per_user': 10
            },
            {
                'title': '₹100 Off Premium Orders',
                'description': 'Get ₹100 discount on orders above ₹1000',
                'reward_type': 'discount',
                'points_required': 1000,
                'discount_amount': Decimal('100.00'),
                'max_redemptions_per_user': 3
            },
            {
                'title': '15% Off Everything',
                'description': 'Get 15% discount on your entire order',
                'reward_type': 'discount',
                'points_required': 1500,
                'discount_percentage': Decimal('15.00'),
                'max_redemptions_per_user': 2
            }
        ]
        
        rewards_created = 0
        
        for reward_data in sample_rewards:
            # Set validity dates
            reward_data['valid_from'] = timezone.now()
            reward_data['valid_until'] = timezone.now() + timedelta(days=365)  # 1 year validity
            reward_data['is_active'] = True
            
            reward, created = LoyaltyReward.objects.get_or_create(
                title=reward_data['title'],
                defaults=reward_data
            )
            
            if created:
                rewards_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Created {rewards_created} sample rewards')
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\n🎉 Loyalty system setup completed!\n'
                'Users will now earn points on delivered orders and can redeem rewards.'
            )
        )
