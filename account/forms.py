from django import forms
from django.contrib.auth.models import User
from .models import Profile
from django.contrib.auth.password_validation import validate_password
from datetime import datetime
from .validators import calculate_age
import logging

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}),
                                    label='username')

class UserRegistrationForm(forms.ModelForm):
    required_css_class = 'required'

    password = forms.CharField(label='Password',
                                widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repeat Password',
                                widget=forms.PasswordInput)

    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    
    class Meta:
        model = User
        fields = ('username','first_name', 'last_name', 'email')
    
    def clean(self):
        cleaned_data = super(UserRegistrationForm, self).clean()
        password1 = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        username = cleaned_data.get('username')
        #validate that the two passwords match each other
        if password1 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        if username in password1:
            raise forms.ValidationError("Password cannot contain your username")


        validate_password(password1)
    #
    # def clean_password(self):
    #     password = self.cleaned_data.get('password')


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
        fields = ('date_of_birth',)

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
        fields = ('date_of_birth', 'address_line_1', 'address_line_2', 'town', 'county', 'postcode')
        # widgets = {'image': forms.HiddenInput()}

