"""
CSV Bulk Import System for Products
"""
import csv
import io
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils.text import slugify
from catalog.models import Product, StoreProduct, Category
from stores.models import Store

@login_required
def bulk_import_products(request):
    """Bulk import products via CSV"""
    # Check if user owns a store
    user_store = Store.objects.filter(owner=request.user).first()
    if not user_store:
        return redirect('stores:dashboard')
    
    if request.method == 'POST':
        return handle_csv_upload(request, user_store)
    
    # Get available categories
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'store': user_store,
        'categories': categories
    }
    
    return render(request, 'stores/bulk_import.html', context)

@require_POST
def handle_csv_upload(request, store):
    """Handle CSV file upload and processing"""
    if 'csv_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'message': 'No CSV file uploaded'
        })
    
    csv_file = request.FILES['csv_file']
    
    # Validate file type
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({
            'success': False,
            'message': 'Please upload a CSV file'
        })
    
    try:
        # Read and process CSV
        csv_data = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # Validate headers
        required_headers = ['name', 'category', 'price', 'weight', 'unit_type']
        if not all(header in csv_reader.fieldnames for header in required_headers):
            return JsonResponse({
                'success': False,
                'message': f'CSV must contain these headers: {", ".join(required_headers)}'
            })
        
        # Process rows
        results = process_csv_rows(csv_reader, store)
        
        return JsonResponse({
            'success': True,
            'message': f'Import completed: {results["created"]} created, {results["updated"]} updated, {results["errors"]} errors',
            'details': results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error processing CSV: {str(e)}'
        })

def process_csv_rows(csv_reader, store):
    """Process each row in the CSV"""
    results = {
        'created': 0,
        'updated': 0,
        'errors': 0,
        'error_details': []
    }
    
    with transaction.atomic():
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because row 1 is headers
            try:
                process_single_row(row, store, results)
            except Exception as e:
                results['errors'] += 1
                results['error_details'].append({
                    'row': row_num,
                    'error': str(e),
                    'data': row
                })
    
    return results

def process_single_row(row, store, results):
    """Process a single CSV row"""
    # Extract and validate data
    name = row['name'].strip()
    category_name = row['category'].strip()
    price_str = row['price'].strip()
    weight_str = row['weight'].strip()
    unit_type = row.get('unit_type', 'grams').strip()
    description = row.get('description', '').strip()
    sku = row.get('sku', '').strip()
    brand = row.get('brand', '').strip()
    stock_quantity_str = row.get('stock_quantity', '0').strip()
    is_featured = row.get('is_featured', '').lower() in ['true', 'yes', '1']
    
    if not all([name, category_name, price_str, weight_str]):
        raise ValueError("Missing required fields: name, category, price, or weight")
    
    # Validate and convert numeric fields
    try:
        price = Decimal(price_str)
        weight = Decimal(weight_str)
        stock_quantity = int(stock_quantity_str) if stock_quantity_str else 0
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid numeric value: {e}")
    
    # Get or create category
    category, created = Category.objects.get_or_create(
        name=category_name,
        defaults={
            'slug': slugify(category_name),
            'is_active': True
        }
    )
    
    # Generate slug for product
    slug = slugify(name)
    
    # Make slug unique if needed
    base_slug = slug
    counter = 1
    while Product.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Get or create product
    product, product_created = Product.objects.get_or_create(
        name=name,
        defaults={
            'slug': slug,
            'description': description or f"Fresh {name.lower()} delivered to your doorstep",
            'category': category,
            'sku': sku,
            'brand': brand,
            'weight_per_unit': weight,
            'unit_type': unit_type,
            'is_active': True
        }
    )
    
    # Create or update store product
    store_product, sp_created = StoreProduct.objects.update_or_create(
        store=store,
        product=product,
        defaults={
            'price': price,
            'stock_quantity': stock_quantity,
            'is_available': True,
            'availability_status': 'in_stock' if stock_quantity > 0 else 'out_of_stock',
            'is_featured': is_featured
        }
    )
    
    if sp_created or product_created:
        results['created'] += 1
    else:
        results['updated'] += 1

def download_sample_csv(request):
    """Download a sample CSV file for bulk import"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_products.csv"'
    
    writer = csv.writer(response)
    
    # Write headers
    writer.writerow([
        'name', 'category', 'price', 'weight', 'unit_type', 
        'description', 'sku', 'brand', 'stock_quantity', 'is_featured'
    ])
    
    # Write sample data
    sample_data = [
        ['Chicken Breast Boneless', 'Chicken', '320', '1000', 'grams', 
         'Fresh boneless chicken breast', 'CHK001', 'Fresh Farm', '50', 'true'],
        ['Fresh Pomfret', 'Seafood', '450', '1000', 'grams', 
         'Fresh pomfret fish', 'FISH001', 'Ocean Fresh', '20', 'true'],
        ['Mutton Curry Cut', 'Mutton', '650', '1000', 'grams', 
         'Fresh mutton curry cut', 'MUT001', 'Premium Meat', '30', 'false'],
        ['Tiger Prawns', 'Seafood', '520', '500', 'grams', 
         'Large tiger prawns', 'PRAWN001', 'Sea Harvest', '25', 'true'],
    ]
    
    for row in sample_data:
        writer.writerow(row)
    
    return response

@login_required
def import_history(request):
    """Show import history for the store"""
    user_store = Store.objects.filter(owner=request.user).first()
    if not user_store:
        return redirect('stores:dashboard')
    
    # Get recent products added to this store
    recent_products = StoreProduct.objects.filter(
        store=user_store
    ).select_related('product').order_by('-created_at')[:50]
    
    context = {
        'store': user_store,
        'recent_products': recent_products
    }
    
    return render(request, 'stores/import_history.html', context)

def validate_csv_data(request):
    """Validate CSV data before actual import"""
    if request.method != 'POST' or 'csv_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'message': 'No CSV file provided'
        })
    
    csv_file = request.FILES['csv_file']
    
    try:
        csv_data = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        validation_results = {
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'errors': []
        }
        
        required_headers = ['name', 'category', 'price', 'weight', 'unit_type']
        
        # Check headers
        if not all(header in csv_reader.fieldnames for header in required_headers):
            return JsonResponse({
                'success': False,
                'message': f'Missing required headers: {required_headers}'
            })
        
        # Validate each row
        for row_num, row in enumerate(csv_reader, start=2):
            validation_results['total_rows'] += 1
            
            try:
                # Basic validation
                if not row['name'].strip():
                    raise ValueError("Product name is required")
                
                if not row['category'].strip():
                    raise ValueError("Category is required")
                
                # Validate price
                Decimal(row['price'])
                
                # Validate weight
                Decimal(row['weight'])
                
                validation_results['valid_rows'] += 1
                
            except Exception as e:
                validation_results['invalid_rows'] += 1
                validation_results['errors'].append({
                    'row': row_num,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'validation_results': validation_results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error validating CSV: {str(e)}'
        })

@login_required
def download_sample_csv(request):
    """Download a sample CSV file for bulk import"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_products.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'name', 'category', 'price', 'weight', 'unit_type', 'description',
        'sku', 'brand', 'stock_quantity', 'is_featured'
    ])
    
    # Write sample data
    sample_data = [
        ['Fresh Chicken Breast', 'Chicken', '250', '500', 'grams', 
         'Premium quality chicken breast, boneless and skinless', 'CB001', 
         'Fresh Farm', '100', 'true'],
        ['Atlantic Salmon Fillet', 'Fish', '800', '300', 'grams',
         'Fresh Atlantic salmon, rich in omega-3', 'SF002',
         'Ocean Fresh', '50', 'false'],
        ['Mutton Leg Piece', 'Mutton', '600', '1000', 'grams',
         'Tender mutton leg pieces, perfect for curry', 'ML003',
         'Premium Meat', '75', 'true'],
        ['Large Prawns', 'Seafood', '450', '250', 'grams',
         'Fresh large prawns, cleaned and deveined', 'PR004',
         'Sea Harvest', '30', 'false'],
        ['Chicken Wings', 'Chicken', '180', '500', 'grams',
         'Fresh chicken wings, great for grilling', 'CW005',
         'Poultry Plus', '80', 'false']
    ]
    
    for row in sample_data:
        writer.writerow(row)
    
    return response

@login_required 
def import_history(request):
    """View import history for the store owner"""
    user_store = Store.objects.filter(owner=request.user).first()
    if not user_store:
        return redirect('stores:dashboard')
    
    # For now, show recent products added by this store
    recent_imports = StoreProduct.objects.filter(
        store=user_store
    ).select_related('product', 'product__category').order_by('-created_at')[:50]
    
    context = {
        'store': user_store,
        'recent_imports': recent_imports,
    }
    
    return render(request, 'stores/import_history.html', context)
