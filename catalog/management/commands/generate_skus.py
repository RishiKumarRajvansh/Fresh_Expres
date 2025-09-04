from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Generate SKUs for products that don\'t have them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without actually saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find products without SKUs
        products_without_sku = Product.objects.filter(sku__isnull=True)
        
        if not products_without_sku.exists():
            self.stdout.write(
                self.style.SUCCESS('All products already have SKUs!')
            )
            return
        
        self.stdout.write(
            f'Found {products_without_sku.count()} products without SKUs:'
        )
        
        for product in products_without_sku:
            # Generate SKU
            new_sku = product.generate_sku()
            
            self.stdout.write(
                f'  - {product.name} ({product.category.name}) -> {new_sku}'
            )
            
            if not dry_run:
                product.sku = new_sku
                product.save(update_fields=['sku'])
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDry run complete. Use without --dry-run to actually generate SKUs.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully generated SKUs for {products_without_sku.count()} products!')
            )
