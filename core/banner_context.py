"""
Context processors for making dynamic content available across templates
"""
from accounts.models import PromotionalBanner


def promotional_banners(request):
    """
    Add promotional banners to template context
    """
    return {
        'home_top_banners': PromotionalBanner.get_active_banners('home_top'),
        'home_middle_banners': PromotionalBanner.get_active_banners('home_middle'),
        'home_bottom_banners': PromotionalBanner.get_active_banners('home_bottom'),
        'loyalty_banners': PromotionalBanner.get_active_banners('loyalty_dashboard'),
        'checkout_banners': PromotionalBanner.get_active_banners('checkout'),
    }
