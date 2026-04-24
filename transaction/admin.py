from django.contrib import admin
from .models import Transaction, TransactionMessage, TransactionCharge, TransactionMessageImage, TransactionImage
from simple_history.admin import SimpleHistoryAdmin

@admin.register(Transaction)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ('transaction_reference', 'user_passive', 'user_aggressive', 'order_passive')

@admin.register(TransactionMessage)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ('user_from','user_to','transaction','description','created')

@admin.register(TransactionMessageImage)
class OrderAdmin(admin.ModelAdmin):
    # list_display = ('user_from','user_to','transaction','description','created')
    pass

@admin.register(TransactionCharge)
class TransactionChargeAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'transaction_fee', 'user_to_pay', 'price')

@admin.register(TransactionImage)
class TransactionImageAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'image')
