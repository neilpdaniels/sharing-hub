from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0016_transaction_feedback_multirating'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='checkout_borrower_confirmed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='checkout_borrower_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='checkout_handover_pin',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='checkout_handover_pin_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='checkout_handover_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='checkout_borrower_confirmed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='transaction',
            name='checkout_borrower_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='transaction',
            name='checkout_handover_pin',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='transaction',
            name='checkout_handover_pin_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='checkout_handover_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
