from django import forms
from common.models import Order, OrderImage, LetPriceBand
from .models import TransactionMessage, TransactionMessageImage
from datetime import datetime, date
import logging

class OrderAddForm(forms.ModelForm):
    required_css_class = 'required'

    expiry_date = forms.DateField(
        label='Available until',
        input_formats=['%d/%m/%Y'],
        widget=forms.DateInput(
            format='%d/%m/%Y',
            attrs={'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off', 'class': 'form-control'}
        ),
        help_text='The listing will expire at the end of this day.',
    )

    description = forms.CharField(
        label='Item description',
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        max_length=500,
    )
    additional_comments = forms.CharField(
        label='Additional comments',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        max_length=500,
    )

    class Meta:
        model = Order
        fields = (
            'let_visibility',
            'expiry_date',
            'price',
            'radius_km',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'collection_policy',
            'delivery_cost',
            'collection_details',
            'max_rental_days',
            'description',
            'additional_comments',
            'postcode',
            'latitude',
            'longitude',
        )
        labels = {
            'let_visibility': 'Who can rent this listing?',
            'price': 'Price per day (£)',
            'radius_km': 'Maximum let radius (km)',
            'deposit': 'Deposit (£)',
            'mates_rates': 'Mates rates — price per day (£)',
            'mates_deposit': 'Mates deposit (£)',
            'collection_policy': 'Collection / delivery',
            'delivery_cost': 'Delivery cost (£)',
            'collection_details': 'Details',
            'max_rental_days': 'Maximum rental duration (days)',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'collection_details': forms.TextInput(attrs={'placeholder': 'e.g. available for collection Mon–Fri 9am–5pm'}),
            'max_rental_days': forms.NumberInput(attrs={'min': 1, 'placeholder': '7'}),
        }


class LetPriceBandForm(forms.ModelForm):
    class Meta:
        model = LetPriceBand
        fields = ('duration_days', 'price_per_day')
        labels = {
            'duration_days': 'Days',
            'price_per_day': '£/day',
        }
        widgets = {
            'duration_days': forms.Select(
                choices=[
                    ('', '— select —'),
                    (3,  'Up to 3 days'),
                    (7,  'Up to 7 days'),
                    (14, 'Up to 14 days'),
                    (30, 'Up to 30 days'),
                    (60, 'Up to 60 days'),
                    (90, 'Up to 90 days'),
                ],
                attrs={'class': 'form-control form-control-sm'},
            ),
            'price_per_day': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0, 'step': '1', 'placeholder': '0'}),
        }

LetPriceBandFormSet = forms.inlineformset_factory(
    Order,
    LetPriceBand,
    form=LetPriceBandForm,
    extra=2,
    can_delete=True,
)


class OrderEditForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Order
        fields = ('direction','quantity', 'expiry_date',
        'price', 'description', 'postcode', 'latitude', 'longitude', 'radius_km')

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity'] 
        if quantity < 1:
            raise forms.ValidationError("Quantity cannot be zero")
        return quantity

class OrderExpireForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ()

class OrderHitForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('quantity',)


class RentalEnquiryForm(forms.Form):
    rental_start_date = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(attrs={'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off'}),
    )
    rental_end_date = forms.DateField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(attrs={'placeholder': 'dd/mm/yyyy', 'autocomplete': 'off'}),
    )
    enquiry_message = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, **kwargs):
        self.blocked_dates = set(kwargs.pop('blocked_dates', set()))
        self.handover_dates = set(kwargs.pop('handover_dates', set()))
        self.expiry_date = kwargs.pop('expiry_date', None)
        self.max_rental_days = kwargs.pop('max_rental_days', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('rental_start_date')
        end = cleaned_data.get('rental_end_date')
        if not start or not end:
            return cleaned_data

        if end < start:
            raise forms.ValidationError('Return date must be on or after the start date.')

        today = date.today()
        if start < today:
            raise forms.ValidationError('Start date cannot be in the past.')

        if self.expiry_date and (start > self.expiry_date or end > self.expiry_date):
            raise forms.ValidationError('Selected dates must be before the listing expiry date.')

        rental_days = (end - start).days + 1
        if self.max_rental_days and rental_days > int(self.max_rental_days):
            raise forms.ValidationError(f'This listing allows a maximum of {self.max_rental_days} day(s) per booking.')

        if start in self.handover_dates or end in self.handover_dates:
            raise forms.ValidationError('Selected start/end date is unavailable for collection or drop-off.')

        from datetime import timedelta
        cur = start
        while cur <= end:
            if cur in self.blocked_dates:
                raise forms.ValidationError('One or more selected dates are unavailable.')
            cur += timedelta(days=1)

        return cleaned_data

class OrderImageForm(forms.ModelForm):
    class Meta:
        model = OrderImage
        fields = ('image', )

class TransactionCreateForm(forms.ModelForm):
    """Form for creating a new transaction with pricing and delivery terms."""
    class Meta:
        from transaction.models import Transaction
        model = Transaction
        fields = ('quantity', 'price', 'friend_price', 'deposit', 'friend_deposit', 'delivery_distance_km')
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'friend_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'deposit': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'friend_deposit': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'delivery_distance_km': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 1000}),
        }

class TransactionMessageAddForm(forms.ModelForm):
    class Meta:
        model = TransactionMessage
        fields = ('subject', 'description')

class TransactionMessageImageForm(forms.ModelForm):
    class Meta:
        model = TransactionMessageImage
        fields = ('image', )
