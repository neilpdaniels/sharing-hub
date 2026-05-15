from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0014_transaction_return_workflow_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_proposal_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_proposal_contested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_proposed_by_lender_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_proposed_return_amount',
            field=models.FloatField(default=0, help_text='Current lender proposal for deposit amount to return', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999999)]),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_proposal_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_proposal_contested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_proposed_by_lender_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_proposed_return_amount',
            field=models.FloatField(default=0, help_text='Current lender proposal for deposit amount to return', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999999)]),
        ),
    ]
