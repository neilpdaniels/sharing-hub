from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TransactionMessage
from .tasks import send_new_message_push_notification


# move into order.save
# @receiver(post_save, sender=Order)
# def update_summary_prices(sender, instance, created, **kwargs):
#     # order = instance
#     logging.error("received order save")
#     updateSummaryPrices(instance)


@receiver(post_save, sender=TransactionMessage)
def trigger_message_push_notification(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.user_from_id == instance.user_to_id:
        return
    send_new_message_push_notification.delay(instance.id)