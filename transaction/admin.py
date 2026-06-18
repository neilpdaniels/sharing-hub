from django.contrib import admin
from .models import (
    DisputeCase,
    PaymentAttempt,
    Transaction,
    TransactionMessage,
    TransactionCharge,
    TransactionMessageImage,
    TransactionImage,
)
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


@admin.register(DisputeCase)
class DisputeCaseAdmin(admin.ModelAdmin):
    list_display = (
        'case_number',
        'transaction',
        'reason_code',
        'status',
        'outcome',
        'owner',
        'raised_by',
        'sla_due_at',
        'escalated_at',
        'resolved_at',
        'closed_at',
    )
    list_filter = ('reason_code', 'status', 'outcome')
    search_fields = ('case_number', 'transaction__transaction_reference', 'summary', 'resolution_notes')
    readonly_fields = ('case_number', 'created', 'amended')


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'transaction', 'failure_point', 'status', 'amount', 'card_brand', 'card_funding')
    list_filter = ('status', 'failure_point', 'card_brand', 'card_funding', 'created_at')
    search_fields = ('transaction__transaction_reference', 'error_message', 'stripe_object_id')
