from django import forms
from django.contrib.auth.models import User
from .models import Friendship


class AddFriendForm(forms.Form):
    email = forms.EmailField(
        label='Email address',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': "Friend's email address",
        })
    )
    username = forms.CharField(
        label='Username',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': "Friend's username",
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').strip().lower()
        username = cleaned_data.get('username', '').strip()
        if not email and not username:
            raise forms.ValidationError("Please enter either an email address or a username.")
        if email and username:
            raise forms.ValidationError("Please enter either an email address or a username, not both.")
        if username:
            if not User.objects.filter(username=username).exists():
                raise forms.ValidationError(f'No user with username "{username}" was found.')
        cleaned_data['email'] = email
        cleaned_data['username'] = username
        return cleaned_data


class FriendshipStatusForm(forms.ModelForm):
    class Meta:
        model = Friendship
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'})
        }
