"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT REGISTRATION FORM
# // ==============================================================================
# // Subsystem: Student Self-Registration Validation
# // Description: Standard Django Form validating all registration inputs,
# //   satisfying database constraints (unique username, email, student_number)
# //   and business integrity checks (program active, year_level <= program duration).
# // ==============================================================================
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.core.models import Profile, Program

User = get_user_model()


class RegistrationForm(forms.Form):
    """
    // [Student Form] Self-Registration Form
    // Handles sanitized input processing, password confirmation, complexity checks,
    // and academic boundary rules.
    """
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Password'}),
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm Password'}),
    )
    student_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Student ID Number'}),
    )
    program_id = forms.IntegerField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    year_level = forms.IntegerField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    registration_proof = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*,.pdf'}),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError('Username is required.')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError('First name is required.')
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError('Last name is required.')
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise forms.ValidationError('Email is required.')
        try:
            validate_email(email)
        except ValidationError:
            raise forms.ValidationError('Enter a valid email address.')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered.')
        return email

    def clean_student_number(self):
        student_number = self.cleaned_data.get('student_number', '').strip()
        if not student_number:
            raise forms.ValidationError('Student ID number is required.')
        if Profile.objects.filter(student_number=student_number).exists():
            raise forms.ValidationError('Student ID number already registered.')
        return student_number

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        username = cleaned_data.get('username')
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        email = cleaned_data.get('email')

        # Password matching & complexity check
        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
            else:
                dummy_user = User(
                    username=username or '',
                    email=email or '',
                    first_name=first_name or '',
                    last_name=last_name or '',
                )
                try:
                    validate_password(password, dummy_user)
                except ValidationError as e:
                    self.add_error('password', ' '.join(e.messages))

        # Academic constraints (program & year level)
        prog_id = cleaned_data.get('program_id')
        year_lvl = cleaned_data.get('year_level')

        program = None
        if prog_id:
            try:
                program = Program.objects.get(pk=prog_id, is_active=True)
                cleaned_data['program'] = program
            except Program.DoesNotExist:
                self.add_error('program_id', 'Selected program is invalid or inactive.')

        if year_lvl and program:
            if year_lvl < 1 or year_lvl > program.years_total:
                self.add_error(
                    'year_level',
                    f'Year level {year_lvl} is invalid for {program.code} (maximum {program.years_total} years).'
                )

        return cleaned_data
