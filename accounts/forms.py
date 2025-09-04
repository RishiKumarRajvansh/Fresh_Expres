from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm
from django.contrib.auth import get_user_model
from locations.models import ZipArea
import re

User = get_user_model()

class PhoneLoginForm(forms.Form):
    """Form for phone-based OTP login"""
    phone_number = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter 10-digit phone number',
            'pattern': '[0-9]{10}',
            'title': 'Please enter a valid 10-digit phone number'
        })
    )
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            
            # Check if it's a valid 10-digit phone number
            if len(phone) == 10 and phone.startswith(('6', '7', '8', '9')):
                return phone
            else:
                raise forms.ValidationError('Please enter a valid 10-digit phone number.')
        return phone

class PhoneRegistrationForm(forms.Form):
    """Form for phone-based registration"""
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your full name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email address'
        })
    )
    phone_number = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter 10-digit phone number',
            'pattern': '[0-9]{10}',
            'title': 'Please enter a valid 10-digit phone number'
        })
    )
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            
            # Check if it's a valid 10-digit phone number
            if len(phone) == 10 and phone.startswith(('6', '7', '8', '9')):
                return phone
            else:
                raise forms.ValidationError('Please enter a valid 10-digit phone number.')
        return phone
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()  # Convert to lowercase and strip whitespace
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('An account with this email already exists.')
        return email

class EmailLoginForm(forms.Form):
    """Form for email-based login (Admin, Store, Delivery)"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email address'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()  # Convert to lowercase and strip whitespace
        return email

class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form for non-customer users"""
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()  # Convert to lowercase and strip whitespace
            # Only allow password reset for non-customer users
            user = User.objects.filter(email=email).exclude(user_type='customer').first()
            if not user:
                raise forms.ValidationError(
                    'Password reset is only available for admin and staff accounts. '
                    'Customer accounts use phone-based login.'
                )
        return email

class MobileLoginForm(forms.Form):
    """Form for mobile number login"""
    mobile_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter mobile number',
            'pattern': '[0-9]{10}',
            'title': 'Please enter a valid 10-digit mobile number'
        })
    )
    
    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number')
        if mobile:
            # Remove any non-digit characters
            mobile = re.sub(r'\D', '', mobile)
            
            # Check if it's a valid Indian mobile number
            if len(mobile) == 10 and mobile.startswith(('6', '7', '8', '9')):
                return mobile
            elif len(mobile) == 13 and mobile.startswith('91') and mobile[2:3] in ['6', '7', '8', '9']:
                return mobile[2:]  # Remove country code
            elif len(mobile) == 12 and mobile.startswith('0') and mobile[1:2] in ['6', '7', '8', '9']:
                return mobile[1:]  # Remove leading zero
            else:
                raise forms.ValidationError('Please enter a valid Indian mobile number (10 digits)')
        return mobile

class OTPVerificationForm(forms.Form):
    """Form for OTP verification"""
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Enter 6-digit OTP',
            'pattern': '[0-9]{6}',
            'style': 'letter-spacing: 0.5em; font-size: 1.5rem;',
            'autocomplete': 'one-time-code'
        })
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp')
        if otp and not otp.isdigit():
            raise forms.ValidationError('OTP must contain only digits')
        return otp

class AddressForm(forms.Form):
    """Form for adding/editing addresses"""
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    
    label = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Address Label (e.g., My Home)'
        })
    )
    address_type = forms.ChoiceField(
        choices=ADDRESS_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    address_line_1 = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'House/Flat No., Building Name'
        })
    )
    address_line_2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Area, Street, Sector, Village (optional)'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City'
        })
    )
    state = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'State'
        })
    )
    zip_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'PIN Code'
        })
    )
    
    def clean_zip_code(self):
        zip_code = self.cleaned_data.get('zip_code')
        if zip_code:
            # Remove any non-digit characters
            zip_code = re.sub(r'\D', '', zip_code)
            
            # Check if it's a valid Indian PIN code (6 digits)
            if len(zip_code) == 6 and zip_code.isdigit():
                return zip_code
            else:
                raise forms.ValidationError('Please enter a valid 6-digit PIN code')
        return zip_code
    landmark = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Landmark (optional)'
        })
    )
    contact_person = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contact Person (optional)'
        })
    )
    contact_phone = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mobile Number (required for delivery)',
            'pattern': '[0-9]{10}',
            'title': 'Please enter a 10-digit mobile number'
        }),
        help_text='Required for delivery coordination'
    )
    is_default = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_contact_phone(self):
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            
            # Check if it's a valid Indian mobile number (10 digits starting with 6-9)
            if len(phone) == 10 and phone.isdigit() and phone[0] in '6789':
                return phone
            else:
                raise forms.ValidationError(
                    'Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9'
                )
        return phone

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=15, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label
            })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        if commit:
            user.save()
        return user

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control'
            })

class StoreRegistrationForm(forms.Form):
    """Form for store owner registration"""
    
    # Store Information
    store_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your store name'
        })
    )
    store_type = forms.ChoiceField(
        choices=[
            ('meat', 'Meat Shop'),
            ('seafood', 'Seafood Market'),
            ('both', 'Fresh Express'),
            ('grocery', 'Grocery Store'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Brief description of your store'
        })
    )
    
    # Owner Information
    owner_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter owner full name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter contact number'
        })
    )
    
    # Store Address
    address = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter complete address'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter city'
        })
    )
    zip_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ZIP/postal code'
        })
    )
    
    # Business Information
    gst_number = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter GST number (optional)'
        })
    )
    
    # Password Fields
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a strong password (min 8 characters)'
        })
    )
    confirm_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
    
    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        return confirm_password
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            if len(phone) < 10:
                raise forms.ValidationError('Please enter a valid phone number.')
        return phone

class DeliveryAgentRegistrationForm(forms.Form):
    """Form for delivery agent registration"""
    
    # Personal Information
    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter contact number'
        })
    )
    emergency_contact = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Emergency contact number'
        })
    )
    
    # Address
    address = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter complete address'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter city'
        })
    )
    zip_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ZIP/postal code'
        })
    )
    
    # Vehicle Information
    vehicle_type = forms.ChoiceField(
        choices=[
            ('bicycle', 'Bicycle'),
            ('scooter', 'Scooter'),
            ('motorcycle', 'Motorcycle'),
            ('car', 'Car'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    vehicle_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter vehicle registration number'
        })
    )
    license_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter driving license number'
        })
    )
    
    # Experience
    experience_years = forms.IntegerField(
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Years of delivery experience'
        })
    )
    
    # Password Fields
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a strong password (min 8 characters)'
        })
    )
    confirm_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
    
    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        return confirm_password
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove any non-digit characters
            phone = re.sub(r'\D', '', phone)
            if len(phone) < 10:
                raise forms.ValidationError('Please enter a valid phone number.')
        return phone
