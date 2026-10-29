"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT SELF-SERVICE PROFILE FORM
# // ==============================================================================
# // Subsystem: Student Portal — Personal Information Maintenance
# // Description: Lets a student update their own display name, email, mobile
# //   number and gender. Institutional fields (student number, program, year
# //   level, approval state) stay read-only — only the registrar may change them.
# ==============================================================================
"""

from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import Profile

User = get_user_model()


class StudentProfileForm(forms.ModelForm):
    """
    // [Student Form] Editable slice of Profile + linked auth User fields.
    """
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name',
            'autocomplete': 'given-name',
        }),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name',
            'autocomplete': 'family-name',
        }),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@example.com',
            'autocomplete': 'email',
        }),
    )

    class Meta:
        model = Profile
        fields = ['phone_number', 'gender']
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09171234567',
                'autocomplete': 'tel',
            }),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['gender'].required = False
        self.fields['gender'].choices = [('', 'Prefer not to say')] + list(Profile.GENDER_CHOICES)
        if user is not None and not self.is_bound:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def clean_first_name(self):
        value = (self.cleaned_data.get('first_name') or '').strip()
        if not value:
            raise forms.ValidationError('First name is required.')
        return value

    def clean_last_name(self):
        value = (self.cleaned_data.get('last_name') or '').strip()
        if not value:
            raise forms.ValidationError('Last name is required.')
        return value

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        existing = User.objects.filter(email__iexact=email)
        if self.user is not None:
            existing = existing.exclude(pk=self.user.pk)
        if existing.exists():
            raise forms.ValidationError('That email address is already used by another account.')
        return email

    def clean_phone_number(self):
        value = (self.cleaned_data.get('phone_number') or '').strip()
        if not value:
            return ''
        allowed = set('0123456789+-() ')
        digits = [ch for ch in value if ch.isdigit()]
        if any(ch not in allowed for ch in value) or len(digits) < 7 or len(digits) > 15:
            raise forms.ValidationError('Enter a valid mobile number (7–15 digits, e.g. 09171234567).')
        return value

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user is not None:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save(update_fields=['first_name', 'last_name', 'email'])
        if commit:
            profile.save()
        return profile
