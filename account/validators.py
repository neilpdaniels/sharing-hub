import logging
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import datetime

def calculate_age(born):
    today = datetime.date.today()
    try: 
        birthday = born.replace(year=today.year)
    except ValueError: # raised when birth date is February 29 and the current year is not a leap year
        birthday = born.replace(year=today.year, month=born.month+1, day=1)
    if birthday > today:
        return today.year - born.year - 1
    else:
        return today.year - born.year

def MinAgeValidator(value):
    # dt=datetime.datetime.strptime(value,'%Y-%m-%d')
    if calculate_age(value) < 18:
        raise ValidationError(
            _('you must be at least 18 years old'),
            params={'value': value},
        )
