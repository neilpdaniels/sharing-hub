from django.db.models.signals import post_save
from django.dispatch import receiver
from common.models import Order, Product
from .tasks import updateSummaryPrices
import logging
from datetime import datetime


# move into order.save
# @receiver(post_save, sender=Order)
# def update_summary_prices(sender, instance, created, **kwargs):
#     # order = instance
#     logging.error("received order save")
#     updateSummaryPrices(instance)