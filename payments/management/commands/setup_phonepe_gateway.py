"""
Management command to setup PhonePe payment gateway
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from payments.models_advanced import PaymentGateway
from decimal import Decimal


class Command(BaseCommand):
    help = 'Setup PhonePe payment gateway configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--merchant-id',
            type=str,
            help='PhonePe Merchant ID',
        )
        parser.add_argument(
            '--salt-key',
            type=str,
            help='PhonePe Salt Key',
        )
        parser.add_argument(
            '--salt-index',
            type=int,
            default=1,
            help='PhonePe Salt Index (default: 1)',
        )
        parser.add_argument(
            '--environment',
            choices=['SANDBOX', 'PRODUCTION'],
            default='SANDBOX',
            help='Environment (SANDBOX or PRODUCTION, default: SANDBOX)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Setting up PhonePe payment gateway...')

        # Get configuration from settings or command arguments
        merchant_id = options.get('merchant_id') or getattr(settings, 'PHONEPE_MERCHANT_ID', None)
        salt_key = options.get('salt_key') or getattr(settings, 'PHONEPE_SALT_KEY', None)
        salt_index = options.get('salt_index') or getattr(settings, 'PHONEPE_SALT_INDEX', 1)
        environment = options.get('environment') or getattr(settings, 'PHONEPE_ENV', 'SANDBOX')

        if not merchant_id:
            raise CommandError('PhonePe Merchant ID is required. Set PHONEPE_MERCHANT_ID in settings or use --merchant-id')
        
        if not salt_key:
            raise CommandError('PhonePe Salt Key is required. Set PHONEPE_SALT_KEY in settings or use --salt-key')

        # Set base URL based on environment
        if environment == 'PRODUCTION':
            base_url = 'https://api.phonepe.com/apis/hermes'
        else:
            base_url = 'https://api-preprod.phonepe.com/apis/pg-sandbox'

        # Create or update PhonePe gateway
        gateway, created = PaymentGateway.objects.update_or_create(
            gateway_type='phonepe',
            defaults={
                'name': 'PhonePe Payment Gateway',
                'api_key': '',  # PhonePe doesn't use separate API key
                'secret_key': salt_key,
                'merchant_id': merchant_id,
                'is_active': True,
                'is_sandbox': (environment == 'SANDBOX'),
                'supports_recurring': False,
                'supports_refunds': True,
                'supports_webhooks': True,
                'min_amount': Decimal('1.00'),
                'max_amount': Decimal('200000.00'),
                'fee_percentage': Decimal('2.00'),
                'fee_fixed': Decimal('2.00'),
                'priority': 1,  # Highest priority
                'additional_config': {
                    'salt_index': salt_index,
                    'base_url': base_url,
                    'environment': environment,
                    'supported_payment_modes': [
                        'UPI',
                        'DEBIT_CARD',
                        'CREDIT_CARD',
                        'NET_BANKING'
                    ]
                }
            }
        )

        # Disable other gateways to make PhonePe the only active one
        PaymentGateway.objects.filter(
            is_active=True
        ).exclude(
            gateway_type='phonepe'
        ).update(is_active=False)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} PhonePe payment gateway successfully!'
            )
        )

        self.stdout.write('\nPhonePe Gateway Configuration:')
        self.stdout.write(f'  Merchant ID: {merchant_id}')
        self.stdout.write(f'  Environment: {environment}')
        self.stdout.write(f'  Base URL: {base_url}')
        self.stdout.write(f'  Salt Index: {salt_index}')
        self.stdout.write(f'  Min Amount: ₹{gateway.min_amount}')
        self.stdout.write(f'  Max Amount: ₹{gateway.max_amount}')
        self.stdout.write(f'  Fee: {gateway.fee_percentage}% + ₹{gateway.fee_fixed}')

        # Show callback URLs that need to be configured in PhonePe dashboard
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        self.stdout.write('\nCallback URLs to configure in PhonePe Dashboard:')
        self.stdout.write(f'  Callback URL: {site_url}/payments/phonepe/callback/')
        self.stdout.write(f'  Webhook URL: {site_url}/payments/phonepe/webhook/')
        self.stdout.write(f'  Refund Webhook URL: {site_url}/payments/phonepe/refund-webhook/')

        self.stdout.write('\nOther gateways have been disabled. Only PhonePe is now active.')

        if environment == 'SANDBOX':
            self.stdout.write(
                self.style.WARNING(
                    '\nNote: Gateway is configured for SANDBOX environment. '
                    'Change PHONEPE_ENV to PRODUCTION for live transactions.'
                )
            )

        self.stdout.write('\nSetup completed successfully!')
