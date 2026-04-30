from django import template
from common.models import Category, Product, Order

register = template.Library()

@register.filter
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError):
        return None

@register.filter
def percent(value, arg):
    try:
        return (float(value) / float(arg)) * 100
    except (ValueError, ZeroDivisionError):
        return None

@register.filter
def index(value, i):
    return value[int(i)]

@register.filter
def classname(obj):
    return obj.__class__.__name__

@register.filter
def is_category(obj):
    return isinstance(obj, Category)

@register.filter
def is_product(obj):
    return isinstance(obj, Product)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def format_price(value):
    """
    Format price to show either 0 decimal places (if whole number) or 2 decimal places.
    Examples:
    - 10.0 -> "10"
    - 10.5 -> "10.50"
    - 10.25 -> "10.25"
    """
    try:
        price = float(value)
        # Check if the price is a whole number
        if price == int(price):
            return str(int(price))
        else:
            return "{:.2f}".format(price)
    except (ValueError, TypeError):
        return value