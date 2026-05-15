from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0013_transactionmessageimage_video_raw_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_borrower_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_handover_pin',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_handover_pin_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_handover_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_lender_confirmed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_lender_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_borrower_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_handover_pin',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_handover_pin_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_handover_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_lender_confirmed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_lender_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
