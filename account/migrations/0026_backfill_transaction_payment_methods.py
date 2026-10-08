from django.db import migrations


def backfill_transaction_cards(apps, schema_editor):
    Transaction = apps.get_model('transaction', 'Transaction')
    PaymentMethod = apps.get_model('account', 'PaymentMethod')

    transactions = Transaction.objects.exclude(stripe_payment_method_id='').filter(
        deposit_card_setup_status='READY',
    )
    for txn in transactions.iterator():
        if not txn.user_aggressive_id or not txn.deposit_card_last4:
            continue
        PaymentMethod.objects.update_or_create(
            stripe_payment_method_id=txn.stripe_payment_method_id,
            defaults={
                'user_id': txn.user_aggressive_id,
                'stripe_setup_intent_id': txn.stripe_setup_intent_id or '',
                'card_brand': txn.deposit_card_brand or 'Card',
                'card_funding': txn.deposit_card_funding or '',
                'card_last4': txn.deposit_card_last4,
                'is_default': not PaymentMethod.objects.filter(user_id=txn.user_aggressive_id).exists(),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('account', '0025_notificationpreference'),
        ('transaction', '0042_transaction_stripe_deposit_transfer'),
    ]

    operations = [migrations.RunPython(backfill_transaction_cards, migrations.RunPython.noop)]
