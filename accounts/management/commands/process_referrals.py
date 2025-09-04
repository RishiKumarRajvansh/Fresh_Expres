from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import UserLoyaltyAccount, LoyaltyTransaction, ReferralProgram

User = get_user_model()


class Command(BaseCommand):
    help = 'Process referral bonuses and create loyalty accounts'

    def handle(self, *args, **options):
        # Create loyalty accounts for users who don't have one
        users_without_loyalty = User.objects.filter(
            user_type='customer'
        ).exclude(
            loyalty_account__isnull=False
        )
        
        created_loyalty_accounts = 0
        for user in users_without_loyalty:
            UserLoyaltyAccount.objects.create(user=user)
            created_loyalty_accounts += 1
            
        if created_loyalty_accounts > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Created {created_loyalty_accounts} loyalty accounts')
            )

        # Process pending referral bonuses
        pending_referrals = ReferralProgram.objects.filter(
            referrer_bonus_given=False,
            referred_first_order__isnull=False
        ).select_related('referrer', 'referred', 'referred_first_order')
        
        processed_bonuses = 0
        for referral in pending_referrals:
            try:
                # Award bonus to referrer
                referrer_loyalty = UserLoyaltyAccount.objects.get(user=referral.referrer)
                referrer_loyalty.add_points(
                    points=100,
                    transaction_type='referral_bonus',
                    reason=f'Referral bonus for inviting {referral.referred.get_full_name() or referral.referred.username}'
                )
                
                # Award bonus to referred user
                referred_loyalty = UserLoyaltyAccount.objects.get(user=referral.referred)
                referred_loyalty.add_points(
                    points=100,
                    transaction_type='signup_bonus',
                    reason='Welcome bonus for joining through referral'
                )
                
                # Mark bonuses as given
                referral.referrer_bonus_given = True
                referral.referred_bonus_given = True
                referral.bonus_awarded_at = timezone.now()
                referral.save()
                
                processed_bonuses += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Processed referral bonus: {referral.referrer.username} -> {referral.referred.username}'
                    )
                )
                
            except UserLoyaltyAccount.DoesNotExist as e:
                self.stdout.write(
                    self.style.ERROR(f'Missing loyalty account for referral: {referral.id} - {e}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing referral {referral.id}: {e}')
                )

        if processed_bonuses > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Processed {processed_bonuses} referral bonuses')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('No pending referral bonuses to process')
            )

        # Summary statistics
        total_referrals = ReferralProgram.objects.count()
        successful_referrals = ReferralProgram.objects.filter(referrer_bonus_given=True).count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nReferral Program Summary:'
                f'\n- Total referrals: {total_referrals}'
                f'\n- Successful referrals: {successful_referrals}'
                f'\n- Conversion rate: {(successful_referrals/total_referrals*100) if total_referrals > 0 else 0:.1f}%'
            )
        )
