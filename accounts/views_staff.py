from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views import View
from django.contrib.auth import get_user_model

from stores.forms import StaffLoginForm
from stores.models import Store, StoreStaff

User = get_user_model()

class StaffLoginView(View):
    """Special login for store staff using Store ID + Staff ID + Password"""
    
    def get(self, request):
        if request.user.is_authenticated and request.user.user_type == 'store_staff':
            return redirect('stores:dashboard')
        
        form = StaffLoginForm()
        return render(request, 'accounts/staff_login.html', {'form': form})
    
    def post(self, request):
        form = StaffLoginForm(request.POST)
        
        if form.is_valid():
            store_id = form.cleaned_data['store_id']
            staff_id = form.cleaned_data['staff_id']
            password = form.cleaned_data['password']
            
            try:
                # Find the store by ID (assuming store ID is the primary key or a specific field)
                store = Store.objects.get(id=int(store_id))
                
                # Find the staff member
                staff = StoreStaff.objects.get(
                    store=store,
                    staff_id=staff_id,
                    is_active=True
                )
                
                # Authenticate the user
                user = authenticate(
                    request,
                    username=staff.user.username,
                    password=password
                )
                
                if user and user.is_active:
                    # Additional check to ensure user is staff for this store
                    if user.user_type == 'store_staff':
                        login(request, user)
                        messages.success(request, f'Welcome back, {user.get_full_name()}!')
                        return redirect('stores:staff_dashboard')
                    else:
                        messages.error(request, 'Invalid user type for staff login.')
                else:
                    messages.error(request, 'Invalid password.')
                    
            except Store.DoesNotExist:
                messages.error(request, 'Invalid Store ID.')
            except StoreStaff.DoesNotExist:
                messages.error(request, 'Invalid Staff ID or staff member not found.')
            except ValueError:
                messages.error(request, 'Invalid Store ID format.')
            except Exception as e:
                messages.error(request, f'Login failed: {str(e)}')
        
        return render(request, 'accounts/staff_login.html', {'form': form})
