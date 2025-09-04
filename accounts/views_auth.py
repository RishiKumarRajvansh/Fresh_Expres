from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
import logging
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse, reverse_lazy
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import random
import string
from .models import User, OTPVerification
from .forms import (
    PhoneLoginForm, PhoneRegistrationForm, StoreRegistrationForm, 
    DeliveryAgentRegistrationForm
)

class CustomerLoginView(View):
    """Email-based login for customers"""
    
    def get(self, request):
        if request.user.is_authenticated and request.user.user_type == 'customer':
            return redirect('core:home')
        return render(request, 'accounts/customer_login.html')
    
    def post(self, request):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        
        if not email or not password:
            context = {'error_message': 'Please enter both email and password.'}
            return render(request, 'accounts/customer_login.html', context)
        
        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            context = {'error_message': 'Please enter a valid email address.'}
            return render(request, 'accounts/customer_login.html', context)
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        
        if user is not None and user.user_type == 'customer':
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                return redirect('core:home')
            else:
                context = {'error_message': 'Your account is inactive. Please contact support.'}
                return render(request, 'accounts/customer_login.html', context)
        else:
            # Check if user exists but wrong password
            user_exists = User.objects.filter(email=email, user_type='customer').exists()
            if user_exists:
                context = {'error_message': 'Invalid password. Please try again.'}
            else:
                context = {'error_message': 'No account found with this email. Please register first.'}
            return render(request, 'accounts/customer_login.html', context)

class CustomerRegistrationView(View):
    """Email-based registration for customers"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        return render(request, 'accounts/customer_register.html')
    
    def post(self, request):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        
        # Get referral code from URL parameter
        referral_code = request.GET.get('ref', '').strip()
        
        context = {}
        
        # Validation
        if not all([first_name, email, password, confirm_password]):
            context['error_message'] = 'Please fill in all required fields.'
            return render(request, 'accounts/customer_register.html', context)
        
        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            context['error_message'] = 'Please enter a valid email address.'
            return render(request, 'accounts/customer_register.html', context)
        
        # Password validation
        if password != confirm_password:
            context['error_message'] = 'Passwords do not match.'
            return render(request, 'accounts/customer_register.html', context)
        
        if len(password) < 6:
            context['error_message'] = 'Password must be at least 6 characters long.'
            return render(request, 'accounts/customer_register.html', context)
        
        # Validate phone number if provided
        if phone_number and (not phone_number.isdigit() or len(phone_number) != 10):
            context['error_message'] = 'Please enter a valid 10-digit phone number.'
            return render(request, 'accounts/customer_register.html', context)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            context['error_message'] = 'An account with this email already exists.'
            return render(request, 'accounts/customer_register.html', context)
        
        # Check if phone number already exists (if provided)
        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            context['error_message'] = 'An account with this phone number already exists.'
            return render(request, 'accounts/customer_register.html', context)

        # Validate referral code if provided
        referrer_user = None
        if referral_code:
            try:
                # Extract user ID from referral code (format: REF123456)
                if referral_code.startswith('REF') and len(referral_code) == 9:
                    user_id = int(referral_code[3:])
                    referrer_user = User.objects.get(id=user_id, user_type='customer')
                else:
                    context['warning_message'] = 'Invalid referral code. Registration will continue without referral bonus.'
            except (ValueError, User.DoesNotExist):
                context['warning_message'] = 'Invalid referral code. Registration will continue without referral bonus.'
        
        try:
            # Create user account
            user = User.objects.create_user(
                username=email,  # Use email as username
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number if phone_number else None,
                user_type='customer',
                email_verified=False  # Can be set to True if you don't want email verification
            )
            
            # Create loyalty account
            from .models import UserLoyaltyAccount
            loyalty_account = UserLoyaltyAccount.objects.create(user=user)
            
            # Handle referral if valid
            if referrer_user:
                from .models import ReferralProgram
                ReferralProgram.objects.create(
                    referrer=referrer_user,
                    referred=user
                )
                
                # Give signup bonus to new user
                loyalty_account.add_points(
                    points=50,
                    transaction_type='signup_bonus',
                    reason='Welcome bonus for joining Fresh Express'
                )
                
                messages.success(request, f'Account created successfully! You\'ve earned 50 welcome points. {referrer_user.first_name or referrer_user.username} will receive a bonus when you make your first order!')
            else:
                # Regular signup bonus
                loyalty_account.add_points(
                    points=25,
                    transaction_type='signup_bonus',
                    reason='Welcome bonus for joining Fresh Express'
                )
                messages.success(request, 'Account created successfully! You\'ve earned 25 welcome points.')
            
            # Login user immediately
            login(request, user)
            return redirect('core:home')
            
        except Exception as e:
            context['error_message'] = f'Error creating account: {str(e)}'
            return render(request, 'accounts/customer_register.html', context)

class EmailLoginView(View):
    """Email-based login for Store Admin and Delivery agents (NOT for main Admin)"""
    
    def get(self, request):
        user_type = request.GET.get('type', 'store')
        # Redirect admin users to proper admin login
        if user_type == 'admin':
            return redirect('/admin/login/')
            
        if request.user.is_authenticated and request.user.user_type != 'customer':
            if user_type == 'store' and request.user.user_type == 'store_owner':
                return redirect('stores:dashboard')
            elif user_type == 'store' and request.user.user_type == 'store_staff':
                return redirect('stores:staff_dashboard')
            elif user_type == 'delivery' and request.user.user_type == 'delivery_agent':
                return redirect('delivery:agent_dashboard')
        
        return render(request, 'accounts/email_login.html', {'user_type': user_type})
    
    def post(self, request):
        email = request.POST.get('email', '').strip().lower()  # Convert to lowercase
        password = request.POST.get('password', '').strip()
        user_type = request.POST.get('user_type', 'store')
        
        # Redirect admin login attempts
        if user_type == 'admin':
            return redirect('/admin/login/')
        
        if not email or not password:
            return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        if not user:
            # Try with email field
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            # Check if user exists but password is wrong vs user doesn't exist
            user_exists = User.objects.filter(email=email).exists()
            
            if not user_exists:
                # User doesn't exist - redirect to registration
                if user_type == 'store':
                    return redirect(f'/accounts/store-register/?error=no_account&email={email}')
                elif user_type == 'delivery':
                    return redirect(f'/accounts/delivery-register/?error=no_account&email={email}')
            
            return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        # Check user type (no admin allowed here)
        allowed_types = {
            'store': ['store_owner', 'store_staff'],
            'delivery': ['delivery_agent']
        }
        
        if user.user_type not in allowed_types.get(user_type, []):
            if user.user_type == 'admin':
                return redirect('/admin/login/')
            else:
                return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        login(request, user)
        
        # Redirect based on user type
        if user_type == 'store':
            if user.user_type == 'store_owner':
                return redirect('stores:dashboard')
            elif user.user_type == 'store_staff':
                return redirect('stores:staff_dashboard')
        elif user_type == 'delivery':
            return redirect('delivery:agent_dashboard')
        
        return redirect('core:home')

class CustomPasswordResetView(PasswordResetView):
    """Custom password reset for non-customer users"""
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        # Only allow password reset for non-customer users
        user = User.objects.filter(email=email).exclude(user_type='customer').first()
        if not user:
            return self.form_invalid(form)
        return super().form_valid(form)

class ResendOTPView(View):
    """Resend OTP for phone authentication"""
    
    def post(self, request):
        phone_number = request.POST.get('phone_number', '').strip()
        
        if not phone_number:
            return JsonResponse({'success': False, 'message': 'Phone number is required.'})
        
        # Delete old OTPs for this phone number
        OTPVerification.objects.filter(phone_number=phone_number, is_verified=False).delete()
        
        # Generate new OTP
        otp = OTPVerification.objects.create(
            phone_number=phone_number,
            otp_type='phone'
        )
        
        # In production, integrate with SMS service
        return JsonResponse({
            'success': True, 
            'message': f'New OTP sent to your phone: {otp.otp_code} (Testing mode)'
        })

class StoreRegistrationView(View):
    """Store registration for new store owners"""
    
    def get(self, request):
        context = {}
        
        # Check if user was redirected from login due to no account
        error = request.GET.get('error')
        email = request.GET.get('email')
        
        if error == 'no_account':
            context['error_message'] = "No Account Exists - Please Register Your Store Account"
            context['suggested_email'] = email
        
        return render(request, 'accounts/store_register.html', context)
    
    def post(self, request):
        # Get form data
        store_name = request.POST.get('store_name', '').strip()
        owner_name = request.POST.get('owner_name', '').strip()
        email = request.POST.get('email', '').strip().lower()  # Convert to lowercase
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        gst_number = request.POST.get('gst_number', '').strip()
        description = request.POST.get('description', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Validate required fields (removed store_type from validation)
        required_fields = [store_name, owner_name, email, phone, address, city, zip_code, password]
        if not all(required_fields):
            return render(request, 'accounts/store_register.html')
        
        # Check password confirmation
        if password != confirm_password:
            return render(request, 'accounts/store_register.html')
        
        # Check password strength
        if len(password) < 8:
            return render(request, 'accounts/store_register.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/store_register.html')
        
        # Store registration data in session for admin review
        registration_data = {
            'store_name': store_name,
            'owner_name': owner_name,
            'email': email,
            'phone': phone,
            'address': address,
            'city': city,
            'zip_code': zip_code,
            'gst_number': gst_number,
            'description': description,
            'status': 'pending_review',
            'submitted_at': timezone.now().isoformat()
        }
        
        # In a real application, you would:
        # 1. Save to a StoreRegistration model
        # 2. Send email notification to admin
        # 3. Create pending approval workflow
        
        # For now, let's create the store owner account directly (you can modify this)
        try:
            # Create user account
            username = f"store_{email.split('@')[0]}"
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,  # Now setting the password
                first_name=owner_name.split(' ')[0],
                last_name=' '.join(owner_name.split(' ')[1:]) if ' ' in owner_name else '',
                phone_number=phone,
                user_type='store_owner',
                is_active=True  # Make account active so they can log in
            )
            
            # Create Store record
            from stores.models import Store
            store_code = f"ST{user.id:04d}"
            store = Store.objects.create(
                owner=user,
                store_code=store_code,
                name=store_name,
                description=description,
                phone_number=phone,
                email=email,
                address_line_1=address,
                city=city,
                state='Delhi',  # Default state - can be made configurable
                zip_code=zip_code,
                status='open',  # Store is immediately operational
                is_active=True
            )
            return redirect('accounts:email_login')
            
        except Exception as e:
            return render(request, 'accounts/store_register.html')

class DeliveryAgentRegistrationView(View):
    """Delivery agent registration for new delivery agents"""
    
    def get(self, request):
        context = {}
        
        # Check if user was redirected from login due to no account
        error = request.GET.get('error')
        email = request.GET.get('email')
        
        if error == 'no_account':
            context['error_message'] = "No Account Exists - Please Register Your Delivery Agent Account"
            context['suggested_email'] = email
        
        return render(request, 'accounts/delivery_register.html', context)
    
    def post(self, request):
        # Get form data
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()  # Convert to lowercase
        phone_number = request.POST.get('phone_number', '').strip()
        emergency_contact = request.POST.get('emergency_contact', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        vehicle_type = request.POST.get('vehicle_type', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        experience_years = request.POST.get('experience_years', '0')
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Validate required fields
        # For bicycles, vehicle_number and license_number are optional
        if vehicle_type == 'bicycle':
            required_fields = [full_name, email, phone_number, address, city, zip_code, 
                              vehicle_type, password]
        else:
            required_fields = [full_name, email, phone_number, address, city, zip_code, 
                              vehicle_type, vehicle_number, license_number, password]
        
        if not all(required_fields):
            return render(request, 'accounts/delivery_register.html')
        
        # Check password confirmation
        if password != confirm_password:
            return render(request, 'accounts/delivery_register.html')
        
        # Check password strength
        if len(password) < 8:
            return render(request, 'accounts/delivery_register.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/delivery_register.html')
        
        # Store registration data in session for admin review
        registration_data = {
            'full_name': full_name,
            'email': email,
            'phone_number': phone_number,
            'emergency_contact': emergency_contact,
            'address': address,
            'city': city,
            'zip_code': zip_code,
            'vehicle_type': vehicle_type,
            'vehicle_number': vehicle_number,
            'license_number': license_number,
            'experience_years': experience_years,
            'status': 'pending_review',
            'submitted_at': timezone.now().isoformat()
        }
        
        # In a real application, you would:
        # 1. Save to a DeliveryAgentApplication model
        # 2. Send email notification to admin
        # 3. Create pending approval workflow
        
        # For now, let's create the delivery agent account directly (you can modify this)
        try:
            # Create user account
            username = f"agent_{email.split('@')[0]}"
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,  # Now setting the password
                first_name=full_name.split(' ')[0],
                last_name=' '.join(full_name.split(' ')[1:]) if ' ' in full_name else '',
                phone_number=phone_number,
                user_type='delivery_agent',
                is_active=True  # Make account active so they can log in
            )
            
            # Create DeliveryAgent record
            from delivery.models import DeliveryAgent
            # For now, assign to first available store (in production, this would be admin-managed)
            from stores.models import Store
            default_store = Store.objects.filter(is_active=True).first()
            
            if default_store:
                agent_id = f"AGT{user.id:04d}"
                delivery_agent = DeliveryAgent.objects.create(
                    user=user,
                    store=default_store,
                    agent_id=agent_id,
                    phone_number=phone_number,
                    emergency_contact=emergency_contact,
                    vehicle_type=vehicle_type,
                    vehicle_number=vehicle_number or 'N/A',  # Use 'N/A' for bicycles
                    license_number=license_number or 'N/A',  # Use 'N/A' for bicycles
                    status='inactive',  # Agent starts as inactive until they go online
                    is_available=False
                )
            return redirect('accounts:email_login')
            
        except Exception as e:
            messages.error(request, f'Error during delivery agent registration: {str(e)}')
            import traceback
            traceback.print_exc()
            context = {
                'error_message': 'Registration failed. Please try again.',
                'suggested_email': email,
                'form_data': request.POST  # To preserve form data
            }
            return render(request, 'accounts/delivery_register.html', context)

class BusinessRegistrationView(View):
    """Business registration landing page for choosing store owner or delivery agent"""
    
    def get(self, request):
        return render(request, 'accounts/business_register.html')

class LogoutView(View):
    """Custom logout view - handles both GET and POST"""
    
    def dispatch(self, request, *args, **kwargs):
        return self.perform_logout(request)
    
    def perform_logout(self, request):
        logger = logging.getLogger(__name__)
        user_type = getattr(request.user, 'user_type', 'customer') if request.user.is_authenticated else 'customer'
        username = getattr(request.user, 'username', None) if request.user.is_authenticated else None
        # Process logout request
        session_key_before = request.session.session_key
        logger.info(f"Logout requested by user={username} type={user_type} method={request.method} session_key_before={session_key_before} cookies={request.COOKIES.keys()}")

        # Perform logout (this should clear the session)
        logout(request)

        # After logout, log session key and whether session data remains
        session_key_after = getattr(request.session, 'session_key', None)
        try:
            session_items_after = dict(request.session.items())
        except Exception:
            session_items_after = None
        logger.info(f"Logout completed for user={username} session_key_after={session_key_after} session_items_after_keys={list(session_items_after.keys()) if session_items_after is not None else None}")

        # Provide a success message so clients see confirmation
        try:
            messages.success(request, 'You have been logged out successfully.')
        except Exception:
            logger.exception('Failed to add logout success message')

        # Redirect based on user type
        if user_type in ['admin']:
            return redirect('/admin/login/')
        elif user_type in ['store_owner', 'store_staff']:
            # Redirect store users to the business email login with type=store
            return redirect(f"{reverse('accounts:email_login')}?type=store")
        elif user_type == 'delivery_agent':
            # Redirect delivery agents to the business email login with type=delivery
            return redirect(f"{reverse('accounts:email_login')}?type=delivery")
        else:  # customer
            return redirect('core:home')
    
    def get(self, request):
        return self.perform_logout(request)
    
    def post(self, request):
        return self.perform_logout(request)
