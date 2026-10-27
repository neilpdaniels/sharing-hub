from datetime import date

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from common.phone_utils import is_valid_uk_phone, normalize_to_domestic
from .form_mixins import AvatarFieldsMixin
from .profanity import username_contains_blocked_word
from .models import Profile
from .validators import calculate_age
import re


UK_POSTCODE_RE = re.compile(
    r'(?:GIR\s?0AA|(?:[A-PR-UWYZ]\d[\dA-HJKSTUW]?|[A-PR-UWYZ][A-HK-Y]\d[\dABEHMNPRVWXY]?)\s?\d[ABD-HJLNP-UW-Z]{2})',
    re.IGNORECASE,
)


def normalize_uk_postcode(value):
    """Validate a full UK postcode and store it in its conventional form."""
    postcode = re.sub(r'\s+', '', (value or '').upper())
    if not UK_POSTCODE_RE.fullmatch(postcode):
        raise forms.ValidationError('Enter a valid UK postcode, for example SW1A 1AA.')
    return f'{postcode[:-3]} {postcode[-3:]}'


def adult_date_input():
    """A native date picker that prevents selecting an underage date in the UI."""
    today = date.today()
    try:
        latest_eligible_date = today.replace(year=today.year - 18)
    except ValueError:  # 29 February in a non-leap year
        latest_eligible_date = today.replace(year=today.year - 18, day=28)
    return forms.DateInput(attrs={
        'type': 'date',
        'max': latest_eligible_date.isoformat(),
        'autocomplete': 'bday',
    })

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}),
                                    label='username')

class UserRegistrationStartForm(AvatarFieldsMixin):
    """User registration form with avatar customization."""
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
    date_of_birth = forms.DateField(
        required=True,
        input_formats=['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'],
        widget=adult_date_input(),
    )
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
        if username_contains_blocked_word(username):
            raise forms.ValidationError('Username not available.')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Username not available.')
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
        normalized = normalize_to_domestic(number)
        if not is_valid_uk_phone(normalized):
            raise forms.ValidationError('Enter a valid UK mobile number.')
        return normalized

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

    def clean_postcode(self):
        return normalize_uk_postcode(self.cleaned_data['postcode'])

    def clean(self):
        cleaned_data = super().clean()
        return self._validate_avatar_options(cleaned_data)


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


class AvatarEditForm(AvatarFieldsMixin):
    """Avatar customization edit form."""

    # Update initial value for avatar_facial_hair (different from registration)
    avatar_facial_hair = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        initial=33,
        widget=forms.NumberInput(attrs={'type': 'range', 'min': 0, 'max': 100, 'step': 1}),
        label='Facial hair'
    )

    def clean(self):
        cleaned_data = super().clean()
        return self._validate_avatar_options(cleaned_data)


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name')
        
# to condense at some point, currently dont want to implement profile addition
# picture functionality
class ProfileAddForm(forms.ModelForm):
    required_css_class = 'required'
    date_of_birth = forms.DateField(
        required=True,
        input_formats=['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'],
        widget=adult_date_input(),
    )

    class Meta:
        model = Profile
        fields = ('date_of_birth', 'mobile_number', 'address_line_1', 'address_line_2', 'town', 'county', 'postcode')
        widgets = {
            'mobile_number': forms.TextInput(attrs={
                'type': 'tel',
                'inputmode': 'tel',
                'autocomplete': 'tel-national',
                'placeholder': 'e.g. 07700 900123',
            }),
            'address_line_1': forms.TextInput(attrs={'autocomplete': 'address-line1'}),
            'address_line_2': forms.TextInput(attrs={'autocomplete': 'address-line2'}),
            'town': forms.TextInput(attrs={'autocomplete': 'address-level2'}),
            'county': forms.TextInput(attrs={'autocomplete': 'address-level1'}),
            'postcode': forms.TextInput(attrs={'autocomplete': 'postal-code'}),
        }

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data['date_of_birth'] 
        if calculate_age(date_of_birth) < 18:
            raise forms.ValidationError("You must be at least 18 to register")
        return date_of_birth

    def clean_mobile_number(self):
        number = (self.cleaned_data.get('mobile_number') or '').strip()
        normalized = normalize_to_domestic(number)
        if not is_valid_uk_phone(normalized):
            raise forms.ValidationError('Enter a valid UK mobile number.')
        return normalized

    def clean_postcode(self):
        return normalize_uk_postcode(self.cleaned_data['postcode'])

class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('image',)

class ProfileEditForm(forms.ModelForm):
    required_css_class = 'required'
    date_of_birth = forms.DateField(
        required=True,
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
        widget=adult_date_input(),
    )

    class Meta:
        model = Profile
        fields = ('date_of_birth', 'mobile_number', 'address_line_1', 'address_line_2', 'town', 'county', 'postcode')
        # widgets = {'image': forms.HiddenInput()}

    def clean_mobile_number(self):
        number = (self.cleaned_data.get('mobile_number') or '').strip()
        normalized = normalize_to_domestic(number)
        if not is_valid_uk_phone(normalized):
            raise forms.ValidationError('Enter a valid UK mobile number.')
        return normalized

    def clean_postcode(self):
        return normalize_uk_postcode(self.cleaned_data['postcode'])
