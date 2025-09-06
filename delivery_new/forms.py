from django import forms
from .models import DeliveryIssue, DeliveryRating, DeliveryAgentZipCoverage
from locations.models import ZipArea

class DeliveryOTPForm(forms.Form):
    """Form for OTP verification"""
    otp = forms.CharField(
        label='OTP',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit OTP',
            'autocomplete': 'off'
        })
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp')
        # Ensure OTP is numeric
        if not otp.isdigit():
            raise forms.ValidationError("OTP must contain only numbers")
        return otp


class DeliveryIssueForm(forms.ModelForm):
    """Form for reporting delivery issues"""
    
    class Meta:
        model = DeliveryIssue
        fields = ['issue_type', 'description']
        widgets = {
            'issue_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please describe the issue in detail'
            })
        }


class DeliveryRatingForm(forms.ModelForm):
    """Form for customer delivery ratings"""
    
    class Meta:
        model = DeliveryRating
        fields = ['rating', 'feedback']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 5
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Tell us about your delivery experience (optional)'
            })
        }


class DeliveryAgentZipCoverageForm(forms.Form):
    """Form for adding ZIP codes to a delivery agent's coverage area"""
    zip_areas = forms.ModelMultipleChoiceField(
        queryset=ZipArea.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'zip-area-checkbox'}),
        required=False,  # Allow empty selection to remove all
        label="Select ZIP codes for your service area"
    )
    
    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent
        
        # If agent is provided, preselect their current ZIP areas
        if agent:
            self.fields['zip_areas'].initial = agent.zip_coverages.filter(
                is_active=True
            ).values_list('zip_area_id', flat=True)
    
    def save(self):
        """Save the selected ZIP areas for the agent"""
        if not self.agent:
            raise ValueError("Agent must be provided to save ZIP coverage")
        
        selected_zip_areas = self.cleaned_data['zip_areas']
        
        # Get currently active ZIP coverages
        current_coverages = self.agent.zip_coverages.filter(is_active=True)
        current_zip_areas = {coverage.zip_area for coverage in current_coverages}
        
        # Deactivate removed ZIP areas
        to_remove = set(current_zip_areas) - set(selected_zip_areas)
        for zip_area in to_remove:
            coverage = self.agent.zip_coverages.filter(zip_area=zip_area).first()
            if coverage:
                coverage.is_active = False
                coverage.save()
        
        # Add new ZIP areas
        to_add = set(selected_zip_areas) - set(current_zip_areas)
        for zip_area in to_add:
            DeliveryAgentZipCoverage.objects.create(
                agent=self.agent,
                zip_area=zip_area,
                is_active=True
            )
        
        # Reactivate existing but inactive ZIP areas
        for zip_area in selected_zip_areas:
            coverage = self.agent.zip_coverages.filter(zip_area=zip_area, is_active=False).first()
            if coverage:
                coverage.is_active = True
                coverage.save()
