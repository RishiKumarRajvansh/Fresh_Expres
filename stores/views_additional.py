from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Store
from accounts.models import User
from core.decorators import StoreRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

@login_required
def store_profile(request):
    """Store profile management"""
    try:
        if request.user.user_type == 'store_owner':
            store = request.user.owned_stores.first()
        else:
            return redirect('core:dashboard_router')
        
        if not store:
            return redirect('core:dashboard_router')
            
        context = {
            'store': store,
            'title': 'Store Profile'
        }
        return render(request, 'stores/store_profile.html', context)
    except Exception as e:
        return redirect('core:dashboard_router')

@login_required  
def business_hours(request):
    """Manage store business hours"""
    try:
        if request.user.user_type == 'store_owner':
            store = request.user.owned_stores.first()
        else:
            return redirect('core:dashboard_router')
            
        if not store:
            return redirect('core:dashboard_router')
            
        if request.method == 'POST':
            # Handle business hours update
            business_hours = {}
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            for day in days:
                is_open = request.POST.get(f'{day}_is_open') == 'on'
                open_time = request.POST.get(f'{day}_open_time', '')
                close_time = request.POST.get(f'{day}_close_time', '')
                
                business_hours[day] = {
                    'is_open': is_open,
                    'open': open_time if is_open else '',
                    'close': close_time if is_open else ''
                }
            
            store.business_hours = business_hours
            store.save()
            return redirect('stores:business_hours')
            
        context = {
            'store': store,
            'title': 'Business Hours'
        }
        return render(request, 'stores/business_hours.html', context)
    except Exception as e:
        return redirect('core:dashboard_router')

@login_required
def store_analytics(request):
    """Store analytics and reports"""
    try:
        if request.user.user_type == 'store_owner':
            store = request.user.owned_stores.first()
        else:
            return redirect('core:dashboard_router')
            
        if not store:
            return redirect('core:dashboard_router')
            
        context = {
            'store': store,
            'title': 'Store Analytics'
        }
        return render(request, 'stores/analytics.html', context)
    except Exception as e:
        return redirect('core:dashboard_router')

@login_required
def create_store(request):
    """Create new store (for store owners)"""
    if request.user.user_type != 'store_owner':
        return redirect('core:home')
    
    # Check if user already has a store
    if request.user.owned_stores.exists():
        return redirect('stores:dashboard')
    
    if request.method == 'POST':
        try:
            # Handle store creation form
            store_data = {
                'name': request.POST.get('name'),
                'description': request.POST.get('description', ''),
                'phone_number': request.POST.get('phone_number'),
                'email': request.POST.get('email'),
                'address_line_1': request.POST.get('address_line_1'),
                'address_line_2': request.POST.get('address_line_2', ''),
                'city': request.POST.get('city'),
                'state': request.POST.get('state'),
                'zip_code': request.POST.get('zip_code'),
                'owner': request.user,
                'store_code': f'ST{Store.objects.count() + 1:04d}',
            }
            
            store = Store.objects.create(**store_data)
            return redirect('stores:dashboard')
            
        except Exception as e:
            pass  # Handle errors silently
    
    context = {
        'title': 'Create Store'
    }
    return render(request, 'stores/create_store.html', context)
