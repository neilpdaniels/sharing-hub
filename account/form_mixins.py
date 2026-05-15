"""Form mixins for shared form functionality and fields."""

import re
from django import forms


# Avatar field choice definitions
AVATAR_HAIR_LENGTH_CHOICES = (
    ('short', 'Short'),
    ('long', 'Long'),
)

AVATAR_EYES_CHOICES = (
    ('default', 'Default'),
    ('happy', 'Happy'),
    ('wink', 'Wink'),
    ('surprised', 'Surprised'),
    ('squint', 'Squint'),
    ('closed', 'Closed'),
)

AVATAR_MOUTH_CHOICES = (
    ('smile', 'Smile'),
    ('default', 'Default'),
    ('serious', 'Serious'),
    ('twinkle', 'Twinkle'),
    ('tongue', 'Tongue'),
)

AVATAR_CLOTHING_CHOICES = (
    ('hoodie', 'Hoodie'),
    ('graphicShirt', 'Graphic shirt'),
    ('overall', 'Overall'),
    ('shirtCrewNeck', 'Crew neck'),
    ('shirtVNeck', 'V-neck'),
    ('blazerAndShirt', 'Blazer + shirt'),
)

AVATAR_ACCESSORIES_CHOICES = (
    ('none', 'None'),
    ('round', 'Round glasses'),
    ('prescription01', 'Prescription 1'),
    ('prescription02', 'Prescription 2'),
    ('wayfarers', 'Wayfarers'),
    ('sunglasses', 'Sunglasses'),
    ('kurt', 'Kurt'),
    ('eyepatch', 'Eyepatch'),
)


class AvatarFieldsMixin(forms.Form):
    """Mixin providing reusable avatar customization fields and validation."""

    # Avatar field definitions
    avatar_preset = forms.CharField(required=False, widget=forms.HiddenInput())
    avatar_hair_color = forms.CharField(required=False, widget=forms.HiddenInput(), initial='')
    avatar_hair_length = forms.ChoiceField(
        required=False,
        choices=AVATAR_HAIR_LENGTH_CHOICES,
        initial='short',
        widget=forms.HiddenInput(),
    )
    avatar_eyes = forms.ChoiceField(
        required=False,
        choices=AVATAR_EYES_CHOICES,
        initial='default',
    )
    avatar_mouth = forms.ChoiceField(
        required=False,
        choices=AVATAR_MOUTH_CHOICES,
        initial='smile',
    )
    avatar_clothing = forms.ChoiceField(
        required=False,
        choices=AVATAR_CLOTHING_CHOICES,
        initial='hoodie',
    )
    avatar_clothes_color = forms.CharField(required=False, widget=forms.HiddenInput(), initial='')
    avatar_accessories = forms.ChoiceField(
        required=False,
        choices=AVATAR_ACCESSORIES_CHOICES,
        initial='none',
    )
    avatar_accessories_color = forms.CharField(required=False, widget=forms.HiddenInput(), initial='')
    avatar_facial_hair = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        initial=25,
        widget=forms.NumberInput(attrs={'type': 'range', 'min': 0, 'max': 100, 'step': 5}),
        label='Facial hair'
    )
    avatar_skin_tone = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=6,
        initial=4,
        widget=forms.NumberInput(attrs={'type': 'range', 'min': 1, 'max': 6, 'step': 1}),
        label='Skin tone'
    )
    avatar_facial_hair_color = forms.CharField(required=False, widget=forms.HiddenInput(), initial='')

    def _validate_avatar_options(self, cleaned_data):
        """Centralized avatar field validation logic."""
        avatar_preset = (cleaned_data.get('avatar_preset') or '').strip()
        avatar_hair_color = (cleaned_data.get('avatar_hair_color') or '').strip().lower()
        avatar_clothes_color = (cleaned_data.get('avatar_clothes_color') or '').strip().lower()
        avatar_accessories_color = (cleaned_data.get('avatar_accessories_color') or '').strip().lower()
        avatar_facial_hair_color = (cleaned_data.get('avatar_facial_hair_color') or '').strip().lower()
        avatar_hair_length = (cleaned_data.get('avatar_hair_length') or 'short').strip()

        if avatar_preset and not re.match(r'^[a-zA-Z0-9_-]{1,64}$', avatar_preset):
            raise forms.ValidationError('Selected avatar value is invalid.')

        if avatar_hair_color and not re.match(r'^(transparent|[a-fA-F0-9]{6})$', avatar_hair_color):
            raise forms.ValidationError('Selected hair color is invalid.')

        if avatar_clothes_color and not re.match(r'^(transparent|[a-fA-F0-9]{6})$', avatar_clothes_color):
            raise forms.ValidationError('Selected clothing color is invalid.')

        if avatar_accessories_color and not re.match(r'^(transparent|[a-fA-F0-9]{6})$', avatar_accessories_color):
            raise forms.ValidationError('Selected eye wear color is invalid.')

        if avatar_facial_hair_color and not re.match(r'^(transparent|[a-fA-F0-9]{6})$', avatar_facial_hair_color):
            raise forms.ValidationError('Selected facial hair color is invalid.')

        if avatar_hair_length not in {'short', 'long'}:
            raise forms.ValidationError('Selected hair length is invalid.')

        return cleaned_data
