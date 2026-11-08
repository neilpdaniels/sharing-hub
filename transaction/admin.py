from django.contrib import admin, messages
from .models import (
    DisputeCase,
    PaymentAttempt,
    StripeSettlement,
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
    list_display = ('id', 'transaction', 'evidence_stage', 'uploaded_at', 'archived_at', 'archive_expires_at', 'active')
    list_filter = ('evidence_stage', 'active', 'archived_at')
    readonly_fields = ('archived_at', 'archive_expires_at', 'archive_manifest')
    actions = ('restore_archived_condition_media',)

    @admin.action(description='Restore selected archived condition media')
    def restore_archived_condition_media(self, request, queryset):
        from .tasks import ConditionMediaArchiveError, restore_archived_condition_media

        restored = 0
        for evidence in queryset.select_related('transaction'):
            try:
                if restore_archived_condition_media(evidence):
                    restored += 1
            except ConditionMediaArchiveError as exc:
                self.message_user(request, f'Evidence #{evidence.pk} was not restored: {exc}', level=messages.ERROR)
        self.message_user(request, f'Restored {restored} condition-media record(s).')

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


@admin.register(StripeSettlement)
class StripeSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'transaction', 'kind', 'status', 'gross_amount', 'stripe_fee',
        'net_transfer_amount', 'platform_shortfall', 'transfer_id', 'updated_at',
    )
    list_filter = ('kind', 'status', 'created_at')
    search_fields = ('transaction__transaction_reference', 'payment_intent_id', 'charge_id', 'transfer_id', 'failure_reason')
    readonly_fields = ('created_at', 'updated_at', 'idempotency_key')
