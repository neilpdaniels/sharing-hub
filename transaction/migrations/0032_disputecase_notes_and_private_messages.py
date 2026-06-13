from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0031_merge_20260610_1837'),
    ]

    operations = [
        migrations.AddField(
            model_name='disputecase',
            name='external_resolution_notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='disputecase',
            name='internal_resolution_notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='historicaltransactionmessage',
            name='private_to_sender',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='transactionmessage',
            name='private_to_sender',
            field=models.BooleanField(default=False, help_text='If true, only the sender and admin should be able to see this message on the transaction view.'),
        ),
    ]
