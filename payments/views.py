from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import PaymentMethod, UPIProvider

@login_required
def payment_methods(request):
    """List all payment methods for the user"""
    methods = PaymentMethod.objects.filter(user=request.user)
    upi_providers = UPIProvider.objects.filter(is_active=True)
    
    context = {
        'payment_methods': methods,
        'upi_providers': upi_providers,
    }
    return render(request, 'payments/payment_methods.html', context)

@login_required
@require_http_methods(["POST"])
def add_payment_method(request):
    """Add a new payment method"""
    try:
        data = json.loads(request.body)
        payment_type = data.get('payment_type')
        
        if payment_type == 'upi':
            method = PaymentMethod.objects.create(
                user=request.user,
                payment_type='upi',
                upi_id=data.get('upi_id')
            )
        elif payment_type == 'card':
            method = PaymentMethod.objects.create(
                user=request.user,
                payment_type='card',
                card_holder_name=data.get('card_holder_name'),
                card_number=data.get('card_number')[-4:],  # Store only last 4 digits
                expiry_month=data.get('expiry_month'),
                expiry_year=data.get('expiry_year'),
                card_type=data.get('card_type', '').lower()
            )
        elif payment_type == 'cod':
            # Check if COD already exists for user
            if not PaymentMethod.objects.filter(user=request.user, payment_type='cod').exists():
                method = PaymentMethod.objects.create(
                    user=request.user,
                    payment_type='cod'
                )
            else:
                return JsonResponse({'success': False, 'message': 'COD already added'})
        
        return JsonResponse({'success': True, 'method_id': method.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def delete_payment_method(request, method_id):
    """Delete a payment method"""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.delete()
    return redirect('payments:payment_methods')

@login_required
def set_default_payment_method(request, method_id):
    """Set a payment method as default"""
    # Remove default from all methods
    PaymentMethod.objects.filter(user=request.user).update(is_default=False)
    
    # Set new default
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.is_default = True
    method.save()
    return redirect('payments:payment_methods')

def payment_options_checkout(request):
    """Payment options for checkout process"""
    if request.user.is_authenticated:
        methods = PaymentMethod.objects.filter(user=request.user)
    else:
        methods = []
    
    # Always allow COD for non-logged in users
    context = {
        'payment_methods': methods,
        'allow_cod': True,
        'allow_online': True,
    }
    return render(request, 'payments/checkout_options.html', context)

@csrf_exempt
def razorpay_callback(request):
    """Handle Razorpay payment callback"""
    if request.method == 'POST':
        try:
            # This would integrate with actual Razorpay
            # For now, just return success
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

def upi_qr_payment(request):
    """Generate UPI QR code for payment"""
    # This would integrate with UPI payment gateway
    context = {
        'merchant_vpa': 'merchant@okaxis',  # Example UPI ID
        'amount': request.GET.get('amount', '0'),
        'order_id': request.GET.get('order_id', ''),
    }
    return render(request, 'payments/upi_qr.html', context)
