from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import LoyaltyReward


class Command(BaseCommand):
    help = 'Create default loyalty rewards'

    def handle(self, *args, **options):
        rewards_data = [
            {
                'title': '₹50 Off Your Next Order',
                'description': 'Get ₹50 discount on orders above ₹500',
                'points_required': 100,
                'reward_type': 'discount',
                'discount_amount': 50.00,
                'total_redemptions_allowed': 100,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=90)
            },
            {
                'title': '₹100 Off Premium Orders',
                'description': 'Get ₹100 discount on orders above ₹1000',
                'points_required': 200,
                'reward_type': 'discount',
                'discount_amount': 100.00,
                'total_redemptions_allowed': 50,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=90)
            },
            {
                'title': 'Free Delivery Voucher',
                'description': 'Free delivery on your next order (any amount)',
                'points_required': 75,
                'reward_type': 'free_delivery',
                'discount_amount': 0.00,
                'total_redemptions_allowed': 200,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=60)
            },
            {
                'title': '₹250 Off Premium Seafood',
                'description': 'Get ₹250 discount on premium seafood orders above ₹2000',
                'points_required': 500,
                'reward_type': 'discount',
                'discount_amount': 250.00,
                'total_redemptions_allowed': 20,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=120)
            },
            {
                'title': '10% Off Entire Order',
                'description': 'Get 10% discount on your entire order (max ₹300 off)',
                'points_required': 300,
                'reward_type': 'discount',
                'discount_percentage': 10.00,
                'total_redemptions_allowed': 30,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=90)
            },
            {
                'title': 'Premium Member Exclusive Deal',
                'description': 'Special discount for loyal customers - ₹500 off on orders above ₹3000',
                'points_required': 1000,
                'reward_type': 'discount',
                'discount_amount': 500.00,
                'total_redemptions_allowed': 10,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=180)
            }
        ]

        created_count = 0
        for reward_data in rewards_data:
            # Check if reward already exists
            existing_reward = LoyaltyReward.objects.filter(
                title=reward_data['title']
            ).first()
            
            if not existing_reward:
                LoyaltyReward.objects.create(**reward_data)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created reward: {reward_data["title"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Reward already exists: {reward_data["title"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} loyalty rewards!')
        )
