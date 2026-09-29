from django import forms
from django.contrib.auth.models import User


class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password',
            'is_staff',
            'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Force all fields required except password
        for field in self.fields:
            if field != 'password':
                self.fields[field].required = True

        # Password required only when creating
        if not self.instance.pk:
            self.fields['password'].required = True

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get('password')

        # Only change password if user entered one
        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user