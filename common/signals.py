from django.db import transaction as db_transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import Order
from common.operational_alerts import is_operational_alert_enabled, send_operational_alert


@receiver(post_save, sender=Order)
def notify_new_order(sender, instance, created, **kwargs):
    if not created or not is_operational_alert_enabled('order'):
        return
    db_transaction.on_commit(
        lambda: send_operational_alert.delay('order', instance.pk)
    )
