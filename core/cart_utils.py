"""
Utility functions for cart and wishlist count management
"""
from orders.models import Cart
from accounts.models import Wishlist


def get_user_counts(user):
    """
    Get current cart and wishlist counts for a user
    Returns: dict with cart_count and wishlist_count
    """
    if not user.is_authenticated:
        return {'cart_count': 0, 'wishlist_count': 0}
    
    # Get total cart items across all active carts
    cart_count = 0
    active_carts = Cart.objects.filter(user=user, is_active=True)
    for cart in active_carts:
        cart_count += cart.total_items
    
    # Get total wishlist items
    wishlist_count = Wishlist.objects.filter(user=user).count()
    
    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count
    }


def update_navbar_counts(request, additional_data=None):
    """
    Get updated counts and merge with additional response data
    """
    counts = get_user_counts(request.user)
    
    if additional_data:
        counts.update(additional_data)
    
    return counts
