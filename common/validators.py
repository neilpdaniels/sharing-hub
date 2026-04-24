import logging
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import datetime

def MaxOrderPriceValidator(value):

    if value > 2500:
        raise ValidationError(
            _('SharingHub currently enforces a maximum item price of £2500, so that all deliveries are insured. Anything of greater value is currently prohibited by the Royal Mail. We are working to allow item prices greater than £2500 and apologise for any inconvenience'),
            params={'value': value},
        )

