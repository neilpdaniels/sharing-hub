from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from common.models import Category, Order, Product

from .views import _bump_catalog_cache_version


@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Order)
def bump_catalog_cache_version(**kwargs):
    _bump_catalog_cache_version()
