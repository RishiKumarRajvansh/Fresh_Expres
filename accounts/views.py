from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, FormView, ListView
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, authenticate
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import CustomUserCreationForm, ProfileUpdateForm, MobileLoginForm, OTPVerificationForm, AddressForm
from .models import OTPVerification, User, UserProfile, Wishlist
from locations.models import Address
from catalog.models import StoreProduct
import random
import json

# Simulate OTP sending (in production, use actual SMS service)
def send_otp_sms(phone_number, otp_code):
    """
    In production, integrate with SMS service like:
    - Twilio
    - AWS SNS
    - MSG91
    - TextLocal
    
    For now, we'll just return True (for development)
    """
    # SMS integration would go here
    return True

class MobileLoginView(FormView):
    """Mobile number login - Step 1"""
    template_name = 'accounts/mobile_login.html'
    form_class = MobileLoginForm
    
    def form_valid(self, form):
        mobile_number = form.cleaned_data['mobile_number']
        
        # Check if user exists with this mobile number
        try:
            user = User.objects.get(phone_number=mobile_number)
        except User.DoesNotExist:
            # Create a new user account
            username = f"user_{mobile_number}"
            user = User.objects.create_user(
                username=username,
                phone_number=mobile_number
            )
        
        # Create OTP
        otp = OTPVerification.create_otp(mobile_number, user=user)
        
        # Send OTP via SMS (simulated)
        if send_otp_sms(mobile_number, otp.otp_code):
            # Store mobile number in session for OTP verification
            self.request.session['login_mobile_number'] = mobile_number
            self.request.session['otp_attempts'] = 0
            return redirect('accounts:verify_otp')
        else:
            return self.form_invalid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs
    
    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, FormView):
    """User profile view"""
    template_name = 'accounts/profile.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class EditProfileView(LoginRequiredMixin, FormView):
    template_name = 'accounts/edit_profile.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class AddAddressView(LoginRequiredMixin, FormView):
    template_name = 'accounts/add_address.html'
    form_class = AddressForm
    success_url = reverse_lazy('accounts:address_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        Address.objects.create(
            user=self.request.user,
            label=form.cleaned_data['label'],
            address_type=form.cleaned_data['address_type'],
            address_line_1=form.cleaned_data['address_line_1'],
            address_line_2=form.cleaned_data.get('address_line_2', ''),
            landmark=form.cleaned_data.get('landmark', ''),
            city=form.cleaned_data['city'],
            state=form.cleaned_data['state'],
            zip_code=form.cleaned_data['zip_code'],
            contact_person=form.cleaned_data.get('contact_person', ''),
            contact_phone=form.cleaned_data.get('contact_phone', ''),
            is_default=form.cleaned_data.get('is_default', False)
        )
        if self.request.GET.get('next') == 'checkout':
            # The 'orders:checkout' URL requires a store_code argument.
            # Get it from the user's active cart.
            try:
                from django.urls import reverse
                from orders.models import Cart
                
                # Get the user's active cart with items
                cart = Cart.objects.filter(
                    user=self.request.user, 
                    is_active=True
                ).prefetch_related('items').filter(items__isnull=False).first()
                
                if cart:
                    checkout_url = reverse('orders:checkout', kwargs={'store_code': cart.store.store_code})
                    return redirect(checkout_url)
                else:
                    # No active cart with items, redirect to cart page
                    return redirect('orders:cart')
            except Exception:
                # Fallback: redirect to cart if anything goes wrong
                return redirect('orders:cart')
        return super().form_valid(form)


class EditAddressView(LoginRequiredMixin, FormView):
    template_name = 'accounts/edit_address.html'
    form_class = AddressForm
    success_url = reverse_lazy('accounts:address_list')

    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs['pk'], user=self.request.user)

    def get_initial(self):
        address = self.get_object()
        return {
            'label': address.label,
            'address_type': address.address_type,
            'address_line_1': address.address_line_1,
            'address_line_2': address.address_line_2,
            'landmark': address.landmark,
            'city': address.city,
            'state': address.state,
            'zip_code': address.zip_code,
            'contact_person': address.contact_person,
            'contact_phone': address.contact_phone,
            'is_default': address.is_default
        }

    def form_valid(self, form):
        address = self.get_object()
        address.label = form.cleaned_data['label']
        address.address_type = form.cleaned_data['address_type']
        address.address_line_1 = form.cleaned_data['address_line_1']
        address.address_line_2 = form.cleaned_data.get('address_line_2', '')
        address.landmark = form.cleaned_data.get('landmark', '')
        address.city = form.cleaned_data['city']
        address.state = form.cleaned_data['state']
        address.zip_code = form.cleaned_data['zip_code']
        address.contact_person = form.cleaned_data.get('contact_person', '')
        address.contact_phone = form.cleaned_data.get('contact_phone', '')
        address.is_default = form.cleaned_data['is_default']
        address.save()
        return super().form_valid(form)


class DeleteAddressView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/delete_address.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs['pk'], user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['address'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        address = self.get_object()
        address.delete()
        return redirect('accounts:address_list')


class WishlistView(LoginRequiredMixin, ListView):
    model = Wishlist
    template_name = 'accounts/wishlist.html'
    context_object_name = 'wishlist_items'
    paginate_by = 20

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('store_product__product', 'store_product__store').prefetch_related('store_product__product__images')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['wishlist_count'] = self.get_queryset().count()
        return context

class AddressListView(LoginRequiredMixin, ListView):
    template_name = 'accounts/address_list.html'
    context_object_name = 'addresses'
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow customers to access address management
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if coming from checkout
        context['from_checkout'] = self.request.GET.get('next') == 'checkout'
        return context

@require_POST
@login_required
def toggle_wishlist_new(request):
    """Clean wishlist toggle API.

    Accepts JSON or form POST with 'store_product_id'. Returns JSON:
    { success: bool, added: bool, action: 'added'|'removed', wishlist_count: int, ... }
    """
    # Basic debug print for server console when running devserver
    try:
        print('TOGGLE_WISHLIST_API_HIT', request.method, request.path, 'CONTENT_TYPE=', request.META.get('CONTENT_TYPE'))
    except Exception:
        pass

    try:
        content_type = (request.content_type or '')
        if content_type.startswith('application/json'):
            raw = request.body.decode('utf-8') if request.body else '{}'
            data = json.loads(raw)
        else:
            data = request.POST

        # Normalize access
        store_product_id = None
        if isinstance(data, dict):
            store_product_id = data.get('store_product_id')
        else:
            store_product_id = data.get('store_product_id')

        if not store_product_id:
            return JsonResponse({'success': False, 'message': 'store_product_id is required'})

        try:
            store_product = StoreProduct.objects.select_related('product', 'store').get(id=store_product_id)
        except StoreProduct.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found'})

        from django.db import transaction

        with transaction.atomic():
            existed = Wishlist.objects.filter(user=request.user, store_product=store_product).first()
            if existed:
                existed.delete()
                added = False
            else:
                Wishlist.objects.create(user=request.user, store_product=store_product)
                added = True

        wishlist_count = Wishlist.objects.filter(user=request.user).count()

        # Update navbar counts if helper exists
        try:
            from core.cart_utils import update_navbar_counts
            counts = update_navbar_counts(request, {'added': added})
        except Exception:
            counts = {}

        payload = {
            'success': True,
            'added': added,
            'action': 'added' if added else 'removed',
            'wishlist_count': wishlist_count,
            **counts
        }

        return JsonResponse(payload)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    # cleaned duplicate/legacy code removed


def remove_from_wishlist(request, wishlist_id):
    """Remove specific item from wishlist - Removed flash messages"""
    if not request.user.is_authenticated:
        return redirect('accounts:customer_login')
    
    try:
        wishlist_item = get_object_or_404(
            Wishlist, 
            id=wishlist_id, 
            user=request.user
        )
        wishlist_item.delete()
    except Exception as e:
        pass  # Silently handle errors
    
    return redirect('accounts:wishlist')


def clear_wishlist(request):
    """Clear entire wishlist - Updated for AJAX support"""
    if not request.user.is_authenticated:
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': False, 'message': 'Authentication required'})
        return redirect('accounts:customer_login')
    
    if request.method == 'POST':
        try:
            Wishlist.objects.filter(user=request.user).delete()
            
            # For AJAX requests, return JSON with updated counts
            if request.headers.get('Content-Type') == 'application/json':
                from core.cart_utils import update_navbar_counts
                response_data = update_navbar_counts(request, {
                    'message': 'All items cleared from wishlist'
                })
                
                return JsonResponse({
                    'success': True,
                    **response_data
                })
            
        except Exception as e:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Error clearing wishlist'})
    
    return redirect('accounts:wishlist')


def toggle_wishlist(request):
    """Legacy wishlist toggle - redirects to new implementation"""
    return toggle_wishlist_new(request)
