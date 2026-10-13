"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC DEPARTMENT & PROGRAM DJANGO FORMS
# // ==============================================================================
# // Subsystem: Academic Validation Layer (Admin)
# // Description: Django ModelForms for Department and Program models.
# //   Encapsulates clean_* methods, uniqueness validation, and form widget
# //   specifications for administration CRUD interfaces.
# // ==============================================================================
"""

from django import forms

from apps.core.models import Department, Program


class DepartmentForm(forms.ModelForm):
    """
    // [Admin Form] Academic Department Create & Update Form
    // Validates code uniqueness (case-insensitive) and name uniqueness.
    """
    class Meta:
        model = Department
        fields = ['code', 'name', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. CITCS',
                'maxlength': '20',
                'required': True,
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. College of Information Technology and Computer Studies',
                'maxlength': '150',
                'required': True,
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise forms.ValidationError('Department code is required.')
        qs = Department.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Department code "{code}" is already in use.')
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Department name is required.')
        qs = Department.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Department name "{name}" is already registered.')
        return name


class ProgramForm(forms.ModelForm):
    """
    // [Admin Form] Degree Program Create & Update Form
    // Validates program code uniqueness, duration boundary (1-8 years), and parent department.
    """
    class Meta:
        model = Program
        fields = ['department', 'code', 'name', 'years_total', 'is_active']
        widgets = {
            'department': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. BSIT',
                'maxlength': '20',
                'required': True,
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Bachelor of Science in Information Technology',
                'maxlength': '150',
                'required': True,
            }),
            'years_total': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '1',
                'max': '8',
                'required': True,
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise forms.ValidationError('Program code is required.')
        qs = Program.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Program code "{code}" already exists.')
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Program name is required.')
        return name

    def clean_years_total(self):
        years = self.cleaned_data.get('years_total')
        if years is None or years < 1 or years > 8:
            raise forms.ValidationError('Program duration must be between 1 and 8 years.')
        return years
