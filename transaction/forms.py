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
    collection_is_not_home_address = forms.BooleanField(
        label='Collection is not at my home address',
        required=False,
    )

    class Meta:
        model = Order
        fields = (
            'let_visibility',
            'verified_users_only',
            'expiry_date',
            'price',
            'radius_km',
            'deposit',
            'mates_rates',
            'mates_deposit',
            'collection_policy',
            'delivery_cost',
            'delivery_within_km',
            'delivery_cost_per_km',
            'collection_details',
            'collection_address',
            'collection_postcode',
            'max_rental_days',
            'description',
            'additional_comments',
            'postcode',
            'latitude',
            'longitude',
        )
        labels = {
            'let_visibility': 'Who can rent this listing?',
            'verified_users_only': 'Verified users only',
            'price': 'Price per day (£)',
            'radius_km': 'Maximum let radius (km)',
            'deposit': 'Deposit (£)',
            'mates_rates': 'Mates rates — price per day (£)',
            'mates_deposit': 'Mates deposit (£)',
            'collection_policy': 'Collection / delivery',
            'delivery_cost': 'Flat delivery fee (£)',
            'delivery_within_km': 'I would deliver up to (km as the crow flies)',
            'delivery_cost_per_km': 'Price per km (£)',
            'collection_details': 'Details',
            'collection_address': 'Collection address',
            'collection_postcode': 'Collection postcode',
            'max_rental_days': 'Maximum rental duration (days)',
        }
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'collection_details': forms.TextInput(attrs={'placeholder': 'e.g. available for collection Mon–Fri 9am–5pm'}),
            'collection_address': forms.TextInput(attrs={'placeholder': 'e.g. Unit 4, 12 High Street, Mobberley'}),
            'collection_postcode': forms.TextInput(attrs={'placeholder': 'e.g. WA16 8NN'}),
            'max_rental_days': forms.NumberInput(attrs={'min': 1, 'placeholder': '7'}),
            'delivery_within_km': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 1000, 'placeholder': '10'}),
            'delivery_cost_per_km': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01, 'placeholder': '0.00'}),
            'delivery_cost': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01, 'placeholder': '0.00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['collection_is_not_home_address'].initial = not self.instance.collection_is_home_address
        self.fields['delivery_within_km'].help_text = 'Delivery is charged per km up to this distance.'
        self.fields['delivery_cost_per_km'].help_text = 'Delivery cost per km (£) within this range.'
        self.fields['delivery_cost'].help_text = 'Flat delivery fee (£) when delivery distance is beyond this range.'
        self.fields['collection_is_not_home_address'].help_text = 'Tick this if buyers should collect from a different address or postcode.'
        self.fields['collection_address'].help_text = 'Shown only when collection is not at your home address.'
        self.fields['collection_postcode'].help_text = 'Collection postcode for this listing.'
        self.fields['max_rental_days'].help_text = (
            'If you allow rentals over 5 days, deposit cards must be Visa or Mastercard credit cards. '
            'Payment cards can still be different.'
        )
        self.fields['verified_users_only'].help_text = (
            'This means the renter must have completed Stripe identity verification. '
            'It checks identity, not a payment card.'
        )

    def clean(self):
        cleaned_data = super().clean()

        collection_policy = cleaned_data.get('collection_policy')
        radius_km = cleaned_data.get('radius_km')
        delivery_within_km = cleaned_data.get('delivery_within_km')
        delivery_cost_per_km = cleaned_data.get('delivery_cost_per_km') or 0
        delivery_cost = cleaned_data.get('delivery_cost') or 0

        if collection_policy == Order.MUST_COLLECT:
            cleaned_data['delivery_within_km'] = None
            cleaned_data['delivery_cost_per_km'] = None
            cleaned_data['delivery_cost'] = None
        else:
            # Delivery pricing must use a single pricing mode.
            if delivery_cost_per_km > 0 and delivery_cost > 0:
                raise forms.ValidationError(
                    'Choose one delivery pricing mode only: either price per km or flat delivery fee.'
                )

            if delivery_cost_per_km > 0 and not delivery_within_km:
                self.add_error(
                    'delivery_within_km',
                    'Delivery up to (km) is required when using price per km.',
                )

            if (
                collection_policy == Order.WILL_DELIVER
                and delivery_within_km
                and radius_km
                and delivery_within_km > radius_km
            ):
                self.add_error(
                    'delivery_within_km',
                    'Delivery distance cannot be greater than Maximum let radius when lender will deliver.',
                )

        collection_is_not_home_address = cleaned_data.get('collection_is_not_home_address')
        cleaned_data['collection_is_home_address'] = not collection_is_not_home_address

        if not collection_is_not_home_address:
            cleaned_data['collection_address'] = ''
            cleaned_data['collection_postcode'] = ''
        else:
            if not (cleaned_data.get('collection_address') or '').strip():
                self.add_error('collection_address', 'Enter the collection address.')
            if not (cleaned_data.get('collection_postcode') or '').strip():
                self.add_error('collection_postcode', 'Enter the collection postcode.')

        return cleaned_data


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

class TransactionCreateForm(forms.Form):
    """Form for creating a new transaction with pricing and delivery terms."""

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    price = forms.FloatField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
    )
    friend_price = forms.FloatField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
    )
    deposit = forms.FloatField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
    )
    friend_deposit = forms.FloatField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
    )
    delivery_distance_km = forms.IntegerField(
        min_value=1,
        max_value=1000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 1000}),
    )

class TransactionMessageAddForm(forms.ModelForm):
    class Meta:
        model = TransactionMessage
        fields = ('subject', 'description')

class TransactionMessageImageForm(forms.ModelForm):
    class Meta:
        model = TransactionMessageImage
        fields = ('image', 'video')
