"""
Enhanced suggestion system with "Complete the Dish" functionality
"""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from catalog.models import Product, StoreProduct, ProductSuggestion, ProductIngredient
from orders.models import Order, OrderItem
from stores.models import Store

def get_product_suggestions(request, store_product_id):
    """Get suggestions for a product"""
    store_product = get_object_or_404(StoreProduct, id=store_product_id)
    product = store_product.product
    store = store_product.store
    
    # Get manually created suggestions
    manual_suggestions = ProductSuggestion.objects.filter(
        product=product,
        is_active=True
    ).select_related('suggested_product')
    
    # Get automatic suggestions based on order history
    auto_suggestions = get_frequently_bought_together(product, store, limit=5)
    
    # Get ingredients for "Complete the Dish"
    dish_ingredients = get_dish_completion_ingredients(product, store)
    
    # Format response
    suggestions_data = []
    
    # Add manual suggestions
    for suggestion in manual_suggestions:
        try:
            suggested_store_product = StoreProduct.objects.get(
                product=suggestion.suggested_product,
                store=store,
                is_available=True
            )
            suggestions_data.append({
                'id': suggested_store_product.id,
                'name': suggested_store_product.product.name,
                'price': float(suggested_store_product.price),
                'image_url': suggested_store_product.product.image.url if suggested_store_product.product.image else None,
                'type': suggestion.get_suggestion_type_display(),
                'weight': suggestion.weight
            })
        except StoreProduct.DoesNotExist:
            continue
    
    # Add automatic suggestions
    for auto_product in auto_suggestions:
        try:
            suggested_store_product = StoreProduct.objects.get(
                product=auto_product,
                store=store,
                is_available=True
            )
            suggestions_data.append({
                'id': suggested_store_product.id,
                'name': suggested_store_product.product.name,
                'price': float(suggested_store_product.price),
                'image_url': suggested_store_product.product.image.url if suggested_store_product.product.image else None,
                'type': 'Frequently Bought Together',
                'weight': 1
            })
        except StoreProduct.DoesNotExist:
            continue
    
    # Add dish completion ingredients
    ingredients_data = []
    for ingredient_data in dish_ingredients:
        ingredients_data.append({
            'id': ingredient_data['store_product'].id,
            'name': ingredient_data['store_product'].product.name,
            'price': float(ingredient_data['store_product'].price),
            'image_url': ingredient_data['store_product'].product.image.url if ingredient_data['store_product'].product.image else None,
            'quantity': ingredient_data['quantity'],
            'is_optional': ingredient_data['is_optional']
        })
    
    return JsonResponse({
        'success': True,
        'product_name': product.name,
        'suggestions': suggestions_data,
        'dish_ingredients': ingredients_data
    })

def get_frequently_bought_together(product, store, limit=5):
    """Get products frequently bought together with the given product"""
    # Find orders that contain this product
    orders_with_product = Order.objects.filter(
        order_items__store_product__product=product,
        order_items__store_product__store=store,
        status='delivered'
    ).values_list('id', flat=True)
    
    if not orders_with_product:
        return Product.objects.none()
    
    # Find other products in these orders
    frequently_bought = Product.objects.filter(
        store_products__order_items__order__id__in=orders_with_product,
        store_products__store=store
    ).exclude(
        id=product.id
    ).annotate(
        frequency=Count('store_products__order_items__order', distinct=True)
    ).filter(
        frequency__gt=1  # Must appear in at least 2 orders
    ).order_by('-frequency')[:limit]
    
    return frequently_bought

def get_dish_completion_ingredients(product, store):
    """Get ingredients to complete the dish for a product"""
    # Get ingredients associated with the product
    product_ingredients = ProductIngredient.objects.filter(
        product=product
    ).select_related('ingredient')
    
    ingredients_data = []
    
    for prod_ingredient in product_ingredients:
        try:
            # Find the ingredient as a product in the store
            ingredient_product = Product.objects.get(
                name__icontains=prod_ingredient.ingredient.name
            )
            
            ingredient_store_product = StoreProduct.objects.get(
                product=ingredient_product,
                store=store,
                is_available=True
            )
            
            ingredients_data.append({
                'store_product': ingredient_store_product,
                'quantity': prod_ingredient.quantity or 'As needed',
                'is_optional': prod_ingredient.is_optional
            })
            
        except (Product.DoesNotExist, StoreProduct.DoesNotExist):
            continue
    
    return ingredients_data

@login_required
@require_POST
def add_suggestion_to_cart(request):
    """Add multiple suggested products to cart"""
    import json
    
    try:
        data = json.loads(request.body)
        main_product_id = data.get('main_product_id')
        suggested_items = data.get('suggested_items', [])
        
        if not main_product_id or not suggested_items:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request data'
            })
        
        from orders.models import Cart, CartItem
        
        added_items = []
        
        for item in suggested_items:
            store_product_id = item.get('store_product_id')
            quantity = item.get('quantity', 1)
            
            try:
                store_product = StoreProduct.objects.get(id=store_product_id)
                
                # Get or create cart for this store
                cart, created = Cart.objects.get_or_create(
                    user=request.user,
                    store=store_product.store,
                    defaults={'is_active': True}
                )
                
                # Get or create cart item
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    store_product=store_product,
                    defaults={
                        'quantity': quantity,
                        'price_at_add': store_product.price
                    }
                )
                
                if not created:
                    cart_item.quantity += quantity
                    cart_item.save()
                
                added_items.append({
                    'name': store_product.product.name,
                    'quantity': quantity
                })
                
            except StoreProduct.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Added {len(added_items)} items to cart',
            'added_items': added_items
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error adding items to cart: {str(e)}'
        })

def complete_dish_suggestions(request, product_id):
    """Get complete dish suggestions for a product"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get the user's selected store
    store_id = request.session.get('selected_store_id')
    if not store_id:
        return JsonResponse({
            'success': False,
            'message': 'No store selected'
        })
    
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Selected store not found'
        })
    
    # Get dish completion data
    dish_ingredients = get_dish_completion_ingredients(product, store)
    
    # Calculate total price
    total_price = sum(
        float(item['store_product'].price) for item in dish_ingredients
    )
    
    # Format ingredients for response
    ingredients_data = []
    for ingredient_data in dish_ingredients:
        ingredients_data.append({
            'id': ingredient_data['store_product'].id,
            'name': ingredient_data['store_product'].product.name,
            'price': float(ingredient_data['store_product'].price),
            'quantity': ingredient_data['quantity'],
            'is_optional': ingredient_data['is_optional'],
            'image_url': ingredient_data['store_product'].product.image.url if ingredient_data['store_product'].product.image else None
        })
    
    return JsonResponse({
        'success': True,
        'product_name': product.name,
        'ingredients': ingredients_data,
        'total_price': total_price,
        'ingredient_count': len(ingredients_data)
    })
