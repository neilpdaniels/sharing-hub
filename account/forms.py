from django import forms
from django.contrib.auth.models import User
from .models import Profile
from django.contrib.auth.password_validation import validate_password
from .validators import calculate_age
import re

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}),
                                    label='username')

class UserRegistrationStartForm(forms.Form):
    required_css_class = 'required'

    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    username = forms.CharField(
        required=True,
        max_length=30,
        min_length=3,
        help_text='3–30 characters. Letters, numbers, hyphens and underscores only.',
    )
    email = forms.EmailField(required=True)
    date_of_birth = forms.DateField(required=True, input_formats=['%d-%m-%Y'])
    mobile_number = forms.CharField(required=True, max_length=20)
    house_name_number = forms.CharField(required=False, max_length=255)
    address_line_1 = forms.CharField(required=True, max_length=255)
    address_line_2 = forms.CharField(required=False, max_length=255)
    town = forms.CharField(required=True, max_length=255)
    county = forms.CharField(required=False, max_length=255)
    postcode = forms.CharField(required=True, max_length=8)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise forms.ValidationError('Only letters, numbers, hyphens and underscores are allowed.')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken.')
        return username

    def clean_first_name(self):
        first_name = self.cleaned_data['first_name'].strip()
        if not first_name:
            raise forms.ValidationError('Please enter your name.')
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data['last_name'].strip()
        if not last_name:
            raise forms.ValidationError('Please enter your surname.')
        return last_name

    def clean_mobile_number(self):
        number = self.cleaned_data['mobile_number'].strip()
        # Strip leading + and country code if user typed +44
        if number.startswith('+44'):
            number = '0' + number[3:].lstrip()
        # If no leading 0, prepend one
        if number and not number.startswith('0'):
            number = '0' + number
        # Remove spaces/dashes for storage
        number = number.replace(' ', '').replace('-', '')
        return number

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email address is already registered.')
        return email

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data['date_of_birth']
        if calculate_age(date_of_birth) < 18:
            raise forms.ValidationError("You must be at least 18 to register")
        return date_of_birth


class UserRegistrationVerifyForm(forms.Form):
    required_css_class = 'required'

    verification_code = forms.CharField(required=True, max_length=6, min_length=6)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repeat Password', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        if password1 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        if password1:
            validate_password(password1)
        return cleaned_data


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name')
        
# to condense at some point, currently dont want to implement profile addition
# picture functionality
class ProfileAddForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Profile
        fields = ('date_of_birth', 'mobile_number', 'address_line_1', 'address_line_2', 'town', 'county', 'postcode')

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data['date_of_birth'] 
        if calculate_age(date_of_birth) < 18:
            raise forms.ValidationError("You must be at least 18 to register")
        return date_of_birth

class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('image',)

class ProfileEditForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Profile
        fields = ('date_of_birth', 'mobile_number', 'address_line_1', 'address_line_2', 'town', 'county', 'postcode')
        # widgets = {'image': forms.HiddenInput()}

    def clean_mobile_number(self):
        number = (self.cleaned_data.get('mobile_number') or '').strip()
        if number.startswith('+44'):
            number = '0' + number[3:].lstrip()
        if number and not number.startswith('0'):
            number = '0' + number
        return number.replace(' ', '').replace('-', '')

