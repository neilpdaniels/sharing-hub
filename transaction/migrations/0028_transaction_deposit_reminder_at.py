from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0027_transaction_deposit_card_funding'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='deposit_reminder_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='deposit_reminder_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
