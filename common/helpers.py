import os
import uuid
from django.utils.deconstruct import deconstructible
from itertools import chain


def is_profile_kyc_verified(profile):
    """
    Determine whether a profile meets current KYC (Know Your Customer) requirements.

    A profile is considered KYC verified if either:
    1. Stripe identity verification is complete, OR
    2. All baseline verifications are complete (email, mobile, address)

    Args:
        profile: A Profile instance

    Returns:
        bool: True if profile meets KYC requirements, False otherwise
    """
    stripe_verified = getattr(profile, 'stripe_identity_verified', False)
    baseline_verified = (
        profile.email_confirmed
        and profile.mobile_verified
        and profile.address_verified
    )
    return bool(stripe_verified or baseline_verified)


def get_best_active_order_by_price(product, direction):
    if direction == 'B':
        return product.order_set.filter(status='A', direction='S').order_by('price').first()
    return product.order_set.filter(status='A', direction='B').order_by('-price').first()


def get_best_x_active_orders_by_price(product, direction, count):
    if direction == 'B':
        return product.order_set.filter(status='A', direction='S').order_by('price')[:count]
    return product.order_set.filter(status='A', direction='B').order_by('-price')[:count]


def get_all_active_orders_by_price(product, direction):
    if direction == 'B':
        return product.order_set.filter(status='A', direction='S').order_by('price')
    return product.order_set.filter(status='A', direction='B').order_by('-price')


# Backward-compatible aliases. Remove after call sites are migrated.
def getBestActiveOrderByPrice(product, direction):
    return get_best_active_order_by_price(product, direction)


def getBestXActiveOrdersByPrice(product, direction, count):
    return get_best_x_active_orders_by_price(product, direction, count)


def getAllActiveOrdersByPrice(product, direction):
    return get_all_active_orders_by_price(product, direction)

# recursively looks for all products
def get_all_products_under_category(category):
    products = list(category.product_set.all())
    child_categories = category.category_set.all().iterator()
    for child in child_categories:
        products = list(chain(products, get_all_products_under_category(child)))
    return products


def getAllProductsUnderCategory(category):
    return get_all_products_under_category(category)

@deconstructible
class RandomFileName(object):
    def __init__(self, path):
        self.path = os.path.join(path, "%s%s")

    def __call__(self, _, filename):
        # @note It's up to the validators to check if it's the correct file type in name or if one even exist.
        extension = os.path.splitext(filename)[1]
        return self.path % (uuid.uuid4(), extension)