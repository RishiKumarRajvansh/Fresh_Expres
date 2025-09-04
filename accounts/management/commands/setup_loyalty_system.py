from django.core.management.base import BaseCommand
from accounts.models import LoyaltyConfiguration, PromotionalBanner
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Setup default loyalty configuration and sample promotional banners'

    def handle(self, *args, **options):
        # Create default loyalty configuration
        config, created = LoyaltyConfiguration.objects.get_or_create(
            name="Default Loyalty Program",
            defaults={
                'points_per_rupee': 1.0,
                'minimum_order_amount': 100,
                'bronze_threshold': 0,
                'silver_threshold': 1000,
                'gold_threshold': 2000,
                'platinum_threshold': 3000,
                'bronze_multiplier': 1.0,
                'silver_multiplier': 1.2,
                'gold_multiplier': 1.5,
                'platinum_multiplier': 2.0,
                'referrer_bonus_points': 100,
                'referee_bonus_points': 50,
                'signup_bonus_points': 25,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created default loyalty configuration')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Default loyalty configuration already exists')
            )

        # Create sample promotional banners
        sample_banners = [
            {
                'title': '🔥 Fresh Arrival Special',
                'description': 'Get 20% OFF on first order above ₹500 • Use code: FRESH20',
                'banner_type': 'offer',
                'background_color': '#ff6b35',
                'text_color': '#ffffff',
                'offer_code': 'FRESH20',
                'discount_percentage': 20.00,
                'minimum_order_amount': 500.00,
                'display_location': 'home_top',
                'display_order': 1,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=30),
                'max_uses': 1000
            },
            {
                'title': '🎉 Festival Special',
                'description': 'Celebrate with premium seafood at 15% off • Use code: FESTIVAL15',
                'banner_type': 'festival',
                'background_color': '#e74c3c',
                'text_color': '#ffffff',
                'offer_code': 'FESTIVAL15',
                'discount_percentage': 15.00,
                'minimum_order_amount': 800.00,
                'display_location': 'home_middle',
                'display_order': 1,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=15),
                'max_uses': 500
            },
            {
                'title': '💰 Save Big on Bulk Orders',
                'description': 'Get ₹200 off on orders above ₹2000 • Use code: BULK200',
                'banner_type': 'offer',
                'background_color': '#27ae60',
                'text_color': '#ffffff',
                'offer_code': 'BULK200',
                'discount_amount': 200.00,
                'minimum_order_amount': 2000.00,
                'display_location': 'home_bottom',
                'display_order': 1,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=45),
                'max_uses': 200
            },
            {
                'title': '⭐ Loyalty Bonus Weekend',
                'description': 'Earn DOUBLE loyalty points on all orders this weekend!',
                'banner_type': 'announcement',
                'background_color': '#9b59b6',
                'text_color': '#ffffff',
                'display_location': 'loyalty_dashboard',
                'display_order': 1,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=7)
            }
        ]

        created_banners = 0
        for banner_data in sample_banners:
            # Check if banner with similar title already exists
            existing_banner = PromotionalBanner.objects.filter(
                title=banner_data['title']
            ).first()
            
            if not existing_banner:
                PromotionalBanner.objects.create(**banner_data)
                created_banners += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created banner: {banner_data["title"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Banner already exists: {banner_data["title"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_banners} promotional banners!')
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nSetup complete! You can now:'
                '\n- Configure loyalty program settings in Django Admin under "Loyalty Configuration"'
                '\n- Manage promotional banners in Django Admin under "Promotional Banner"'
                '\n- View dynamic banners on the home page and loyalty dashboard'
            )
        )
