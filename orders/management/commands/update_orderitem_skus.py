from django.core.management.base import BaseCommand
from orders.models import OrderItem


class Command(BaseCommand):
    help = 'Update OrderItem product_sku field with current product SKUs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find order items where product_sku is null but product has SKU
        order_items_to_update = OrderItem.objects.filter(
            product_sku__isnull=True,
            store_product__product__sku__isnull=False
        ).select_related('store_product__product')
        
        if not order_items_to_update.exists():
            self.stdout.write(
                self.style.SUCCESS('All order items already have SKUs or products don\'t have SKUs!')
            )
            return
        
        self.stdout.write(
            f'Found {order_items_to_update.count()} order items to update:'
        )
        
        updated_count = 0
        for item in order_items_to_update:
            product = item.store_product.product
            
            self.stdout.write(
                f'  - Order {item.order.order_number}: {item.product_name} -> SKU: {product.sku}'
            )
            
            if not dry_run:
                item.product_sku = product.sku
                item.save(update_fields=['product_sku'])
                updated_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDry run complete. Use without --dry-run to actually update order items.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully updated {updated_count} order items!')
            )
