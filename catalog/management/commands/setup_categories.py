from django.core.management.base import BaseCommand
from catalog.models import Category
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Create initial product categories for the Fresh Express platform'

    def handle(self, *args, **options):
        categories_data = [
            {
                'name': 'Fresh Express',
                'description': 'Premium fresh food including quality meats and seafood',
                'sort_order': 1,
                'subcategories': [
                    {'name': 'Beef', 'description': 'Fresh beef cuts and ground beef'},
                    {'name': 'Chicken', 'description': 'Fresh chicken parts and whole chicken'},
                    {'name': 'Lamb', 'description': 'Premium lamb cuts'},
                    {'name': 'Pork', 'description': 'Fresh pork cuts and specialty items'},
                ]
            },
            {
                'name': 'Seafood',
                'description': 'Fresh fish and seafood delivered daily',
                'sort_order': 2,
                'subcategories': [
                    {'name': 'Fish', 'description': 'Fresh fish fillets and whole fish'},
                    {'name': 'Shellfish', 'description': 'Fresh crabs, lobsters, and shrimp'},
                    {'name': 'Prawns & Shrimp', 'description': 'Fresh and frozen prawns and shrimp'},
                ]
            },
            {
                'name': 'Dairy Products',
                'description': 'Fresh dairy products and eggs',
                'sort_order': 3,
                'subcategories': [
                    {'name': 'Milk & Cream', 'description': 'Fresh milk and dairy cream'},
                    {'name': 'Cheese', 'description': 'Artisan and specialty cheeses'},
                    {'name': 'Eggs', 'description': 'Farm fresh eggs'},
                    {'name': 'Butter & Yogurt', 'description': 'Fresh butter and yogurt products'},
                ]
            },
            {
                'name': 'Prepared Foods',
                'description': 'Ready-to-cook and marinated products',
                'sort_order': 4,
                'subcategories': [
                    {'name': 'Marinated Meats', 'description': 'Pre-marinated meats ready to cook'},
                    {'name': 'Sausages', 'description': 'Fresh and cured sausages'},
                    {'name': 'Deli Items', 'description': 'Sliced meats and prepared foods'},
                ]
            },
            {
                'name': 'Frozen Items',
                'description': 'Premium frozen meat and seafood',
                'sort_order': 5,
                'subcategories': [
                    {'name': 'Frozen Meat', 'description': 'High-quality frozen meat products'},
                    {'name': 'Frozen Seafood', 'description': 'Frozen fish and shellfish'},
                ]
            },
        ]

        created_count = 0
        updated_count = 0

        for category_data in categories_data:
            # Create or get main category
            category, created = Category.objects.get_or_create(
                name=category_data['name'],
                defaults={
                    'slug': slugify(category_data['name']),
                    'description': category_data['description'],
                    'sort_order': category_data['sort_order'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created main category: {category.name}')
                )
            else:
                updated_count += 1
                # Update description and sort order if category exists
                category.description = category_data['description']
                category.sort_order = category_data['sort_order']
                category.save()
                self.stdout.write(
                    self.style.WARNING(f'Updated main category: {category.name}')
                )

            # Create subcategories
            for sub_data in category_data.get('subcategories', []):
                # Check if subcategory already exists with this name
                try:
                    subcategory = Category.objects.get(name=sub_data['name'])
                    # Update existing subcategory
                    subcategory.parent = category
                    subcategory.description = sub_data['description']
                    subcategory.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  Updated subcategory: {subcategory.name}')
                    )
                except Category.DoesNotExist:
                    # Create new subcategory
                    subcategory = Category.objects.create(
                        name=sub_data['name'],
                        slug=slugify(sub_data['name']),
                        parent=category,
                        description=sub_data['description'],
                        is_active=True,
                        sort_order=0,
                    )
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  Created subcategory: {subcategory.name}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCategories setup complete!\n'
                f'Created: {created_count} categories\n'
                f'Updated: {updated_count} categories\n\n'
                f'You can now:\n'
                f'1. Go to /admin/catalog/category/ to manage categories\n'
                f'2. Store managers can select from these categories when adding products\n'
                f'3. Customers can filter products by these categories\n'
            )
        )
