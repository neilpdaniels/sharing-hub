from django.contrib.auth.signals import user_logged_out
from django.contrib.auth.signals import user_logged_in
from django.contrib import messages
from django.dispatch import receiver
from transaction.tasks import createNewTransaction, getUserTransactions

@receiver(user_logged_out)
def show_logout_message(sender, user, request, **kwargs):
    return

@receiver(user_logged_in)
def show_login_message(sender, user, request, **kwargs):
    getUserTransactions.delay(int(user.id))
    request.session['show_txn_login_notice'] = True
