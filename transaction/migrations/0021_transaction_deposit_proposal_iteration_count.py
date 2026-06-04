from django.db import migrations, models
import django.core.validators


def backfill_deposit_proposal_iteration_count(apps, schema_editor):
    Transaction = apps.get_model('transaction', 'Transaction')
    TransactionMessage = apps.get_model('transaction', 'TransactionMessage')

    for txn in Transaction.objects.all().iterator():
        count = TransactionMessage.objects.filter(
            transaction_id=txn.id,
            user_from_id=txn.user_passive_id,
            subject__startswith='Deposit return proposal',
        ).count()
        if count > 5:
            count = 5
        if txn.deposit_proposal_iteration_count != count:
            txn.deposit_proposal_iteration_count = count
            txn.save(update_fields=['deposit_proposal_iteration_count', 'amended'])


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0020_transactionmessageimage_evidence_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_proposal_iteration_count',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Number of lender deposit proposal iterations used (max 5)',
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)],
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_proposal_iteration_count',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Number of lender deposit proposal iterations used (max 5)',
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)],
            ),
        ),
        migrations.RunPython(
            backfill_deposit_proposal_iteration_count,
            migrations.RunPython.noop,
        ),
    ]
