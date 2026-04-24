from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ReferencePrice
from common.models import Order, Product
import logging
from datetime import datetime

@receiver(post_save, sender=ReferencePrice)
def update_orders(sender, instance, created, **kwargs):
    # only update if price update - would need to use pre_save - leave as is for now
    
    # for each product which has this reference price type
    # get orders where they are open, quantity is > 0 , they have a ref price type    
    products = Product.objects.all().filter(reference_price_model = instance)
    for product in products:
        orders = product.order_set.filter(status='A', quantity__gt=0, price_style__exact='R')
        for order in orders:
            newPx = round((((product.reference_price_pct/100) * instance.gbp_price) * (order.relative_price_pct/100) + order.relative_offset),2)
            order.price = newPx
            order.save()
