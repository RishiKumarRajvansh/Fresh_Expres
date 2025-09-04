from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, FormView, ListView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import uuid
import json
from locations.models import ZipArea
from stores.models import Store, StoreZipCoverage
from catalog.models import Category, Product, StoreProduct
from .models import FAQ, FAQCategory, ChatConversation, ChatMessage, BotResponse, ContactMessage
from .chat_views import FAQListView, chat_start, chat_messages, chat_close
from django import forms

class ZipCaptureForm(forms.Form):
    zip_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your ZIP code',
            'required': True
        })
    )

class HomeView(TemplateView):
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get selected ZIP from session
        selected_zip = self.request.session.get('selected_zip_code')
        
        if selected_zip:
            try:
                zip_area = ZipArea.objects.get(zip_code=selected_zip, is_active=True)
                
                # Find the best store for this ZIP (Blinkit-style automatic selection)
                best_store = self.get_best_store_for_zip(zip_area)
                
                if best_store:
                    # Store the selected store in session for seamless experience
                    self.request.session['selected_store_id'] = best_store.id
                    
                    # Get featured products from the selected store
                    featured_products = StoreProduct.objects.filter(
                        store=best_store,
                        is_featured=True,
                        is_available=True,
                        availability_status='in_stock'
                    ).select_related('product', 'store')[:12]
                    
                    # Get fresh arrivals (recently added products)
                    fresh_arrivals = StoreProduct.objects.filter(
                        store=best_store,
                        is_available=True,
                        availability_status='in_stock'
                    ).select_related('product', 'product__category', 'store').order_by('-created_at')[:8]
                    
                    # Get best sellers - first try featured products, then fall back to any available
                    best_sellers = StoreProduct.objects.filter(
                        store=best_store,
                        is_available=True,
                        availability_status='in_stock',
                        is_featured=True
                    ).select_related('product', 'product__category', 'store').order_by('-updated_at')[:8]
                    
                    # If no featured products, get any available products as best sellers
                    if not best_sellers:
                        best_sellers = StoreProduct.objects.filter(
                            store=best_store,
                            is_available=True,
                            availability_status='in_stock'
                        ).select_related('product', 'product__category', 'store').order_by('-updated_at')[:8]
                    
                    # Get all active categories for now (simplified)
                    categories = Category.objects.filter(
                        is_active=True,
                        parent__isnull=True
                    ).exclude(
                        slug__isnull=True
                    ).exclude(
                        slug__exact=''
                    ).order_by('sort_order')[:8]
                    
                    # Get user's wishlist items if authenticated
                    wishlist_items = []
                    if self.request.user.is_authenticated:
                        from accounts.models import Wishlist
                        wishlist_items = list(Wishlist.objects.filter(
                            user=self.request.user
                        ).values_list('store_product_id', flat=True))
                    
                    context.update({
                        'zip_area': zip_area,
                        'selected_store': best_store,
                        'store': best_store,  # For next delivery template
                        'featured_products': featured_products,
                        'fresh_arrivals': fresh_arrivals,
                        'best_sellers': best_sellers,
                        'categories': categories,
                        'wishlist_items': wishlist_items,
                        'delivery_info': self.get_delivery_info(best_store, zip_area),
                        'next_delivery_slot': self.get_next_delivery_slot(best_store, zip_area),
                    })
                else:
                    # No store serves this ZIP - show empty state
                    context.update({
                        'no_service': True,
                        'zip_area': zip_area,
                        'fresh_arrivals': [],
                        'best_sellers': [],
                        'featured_products': [],
                        'categories': Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order')[:8],
                    })
                    
            except ZipArea.DoesNotExist:
                context.update({
                    'invalid_zip': True,
                    'fresh_arrivals': [],
                    'best_sellers': [],
                    'featured_products': [],
                    'categories': Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order')[:8],
                })
        else:
            # No ZIP selected - show empty state
            context.update({
                'fresh_arrivals': [],
                'best_sellers': [],
                'featured_products': [],
                'categories': Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order')[:8],
            })
        
        return context
    
    def get_best_store_for_zip(self, zip_area):
        """
        Find the best store for a ZIP code based on:
        1. Active stores that serve this ZIP
        2. Currently open stores
        3. Store with best delivery time/rating (can be enhanced)
        """
        available_stores = Store.objects.filter(
            zip_coverages__zip_area=zip_area,
            zip_coverages__is_active=True,
            is_active=True,
            status='open'
        ).select_related().order_by('name')  # Can add ordering by rating, delivery time, etc.
        
        # Return the first available store (can be enhanced with better logic)
        for store in available_stores:
            if store.is_open:  # Uses the is_open property that checks business hours
                return store
        
        return None
    
    def get_delivery_info(self, store, zip_area):
        """Get delivery information for the store-ZIP combination"""
        try:
            coverage = StoreZipCoverage.objects.get(store=store, zip_area=zip_area)
            return {
                'delivery_fee': coverage.get_delivery_fee(),
                'min_order_value': coverage.get_min_order_value(),
                'delivery_time': coverage.get_delivery_time(),
            }
        except StoreZipCoverage.DoesNotExist:
            return None
    
    def get_next_delivery_slot(self, store, zip_area):
        """Get the next available delivery slot for the store-ZIP combination"""
        from stores.models import DeliverySlot
        from datetime import datetime, time
        
        try:
            # Get current time
            now = timezone.now().time()
            
            # Find delivery slots for this store and zip area
            available_slots = DeliverySlot.objects.filter(
                store=store,
                zip_area=zip_area,
                is_active=True,
                start_time__gt=now  # Only future slots
            ).order_by('start_time')
            
            return available_slots.first()
        except Exception as e:
                        return None
    
    def dispatch(self, request, *args, **kwargs):
        # Check if ZIP code is selected
        if not request.session.get('selected_zip_code'):
            return redirect('core:zip_capture')
        return super().dispatch(request, *args, **kwargs)

class ZipCaptureView(FormView):
    template_name = 'core/zip_capture.html'
    form_class = ZipCaptureForm
    success_url = reverse_lazy('core:home')
    
    def form_valid(self, form):
        zip_code = form.cleaned_data['zip_code']
        
        try:
            zip_area = ZipArea.objects.get(zip_code=zip_code, is_active=True)
            self.request.session['selected_zip_code'] = zip_code
            return super().form_valid(form)
        except ZipArea.DoesNotExist:
            form.add_error('zip_code', 'Sorry, we don\'t deliver to this ZIP code yet.')
            # Optionally add to waitlist
            return self.form_invalid(form)

class ChangeZipView(FormView):
    template_name = 'core/change_zip.html'
    form_class = ZipCaptureForm
    success_url = reverse_lazy('core:home')
    
    def form_valid(self, form):
        zip_code = form.cleaned_data['zip_code']
        
        try:
            zip_area = ZipArea.objects.get(zip_code=zip_code, is_active=True)
            self.request.session['selected_zip_code'] = zip_code
            # Clear any previously selected store
            if 'selected_store_id' in self.request.session:
                del self.request.session['selected_store_id']
            return super().form_valid(form)
        except ZipArea.DoesNotExist:
            form.add_error('zip_code', 'Sorry, we don\'t deliver to this ZIP code yet.')
            return self.form_invalid(form)

# Basic template views
class AboutView(TemplateView):
    template_name = 'core/about.html'

class ContactView(TemplateView):
    template_name = 'core/contact.html'

class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'

class TermsView(TemplateView):
    template_name = 'core/terms.html'

class WaitlistView(TemplateView):
    template_name = 'core/waitlist.html'
    success_url = reverse_lazy('core:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_zip = self.request.session.get('selected_zip_code')
        if current_zip:
            try:
                context['current_zip_area'] = ZipArea.objects.get(
                    zip_code=current_zip, 
                    is_active=True
                )
            except ZipArea.DoesNotExist:
                pass
        return context
    
    def form_valid(self, form):
        zip_code = form.cleaned_data['zip_code']
        
        try:
            zip_area = ZipArea.objects.get(zip_code=zip_code, is_active=True)
            self.request.session['selected_zip_code'] = zip_code
            return super().form_valid(form)
        except ZipArea.DoesNotExist:
            form.add_error('zip_code', 'Sorry, we don\'t deliver to this ZIP code yet.')
            return self.form_invalid(form)

class WaitlistView(FormView):
    template_name = 'core/waitlist.html'
    form_class = ZipCaptureForm
    success_url = reverse_lazy('core:home')
    
    def form_valid(self, form):
        zip_code = form.cleaned_data['zip_code']
        return super().form_valid(form)

class AboutView(TemplateView):
    template_name = 'core/about.html'

class ContactView(TemplateView):
    template_name = 'core/contact.html'

class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'

class TermsView(TemplateView):
    template_name = 'core/terms.html'

class ChatSupportView(TemplateView):
    template_name = 'core/chat_support.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Chat Support - AI Assistant'
        return context
