from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.contrib.auth.signals import user_logged_in
from django.db import transaction as db_transaction
from django.db.models.signals import post_save
from django.contrib import messages
from django.dispatch import receiver
from transaction.tasks import createNewTransaction, getUserTransactions
from common.operational_alerts import is_operational_alert_enabled, send_operational_alert


@receiver(post_save, sender=get_user_model())
def notify_new_user_registration(sender, instance, created, **kwargs):
    if not created or not is_operational_alert_enabled('user_registration'):
        return
    db_transaction.on_commit(
        lambda: send_operational_alert.delay('user_registration', instance.pk)
    )

@receiver(user_logged_out)
def show_logout_message(sender, user, request, **kwargs):
    return

@receiver(user_logged_in)
def show_login_message(sender, user, request, **kwargs):
    getUserTransactions.delay(int(user.id))
    request.session['show_txn_login_notice'] = True
