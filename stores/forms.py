from django import forms
from django.contrib.auth import get_user_model
from locations.models import ZipArea
from stores.models import StoreZipCoverage
from delivery.models import DeliveryAgentZipCoverage

User = get_user_model()

class StoreZipCoverageForm(forms.Form):
    """Form for store managers to select ZIP areas they want to serve"""
    zip_areas = forms.ModelMultipleChoiceField(
        queryset=ZipArea.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all ZIP areas where you want to deliver products"
    )
    
    def __init__(self, *args, **kwargs):
        self.store = kwargs.pop('store', None)
        super().__init__(*args, **kwargs)
        
        if self.store:
            # Pre-select currently covered ZIP areas
            current_zip_areas = ZipArea.objects.filter(
                store_coverages__store=self.store,
                store_coverages__is_active=True
            )
            self.fields['zip_areas'].initial = current_zip_areas
    
    def save(self):
        if not self.store:
            return
        
        selected_zip_areas = self.cleaned_data['zip_areas']
        
        # Deactivate all current coverages
        StoreZipCoverage.objects.filter(store=self.store).update(is_active=False)
        
        # Create/activate coverage for selected areas
        for zip_area in selected_zip_areas:
            coverage, created = StoreZipCoverage.objects.get_or_create(
                store=self.store,
                zip_area=zip_area,
                defaults={'is_active': True}
            )
            if not created:
                coverage.is_active = True
                coverage.save()


class DeliveryAgentZipCoverageForm(forms.Form):
    """Form for delivery agents to select ZIP areas they can serve"""
    zip_areas = forms.ModelMultipleChoiceField(
        queryset=ZipArea.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all ZIP areas where you can deliver orders"
    )
    
    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        if self.agent:
            # Pre-select currently covered ZIP areas
            current_zip_areas = ZipArea.objects.filter(
                delivery_agent_coverages__agent=self.agent,
                delivery_agent_coverages__is_active=True
            )
            self.fields['zip_areas'].initial = current_zip_areas
    
    def save(self):
        if not self.agent:
            return
        
        selected_zip_areas = self.cleaned_data['zip_areas']
        
        # Deactivate all current coverages
        DeliveryAgentZipCoverage.objects.filter(agent=self.agent).update(is_active=False)
        
        # Create/activate coverage for selected areas
        for zip_area in selected_zip_areas:
            coverage, created = DeliveryAgentZipCoverage.objects.get_or_create(
                agent=self.agent,
                zip_area=zip_area,
                defaults={'is_active': True}
            )
            if not created:
                coverage.is_active = True
                coverage.save()
