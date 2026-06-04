from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0017_transaction_checkout_workflow_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionmessageimage',
            name='capture_device',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='captured_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='checksum_sha256',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='evidence_stage',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='external_video_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='uploader_role',
            field=models.CharField(blank=True, choices=[('lender', 'Lender'), ('borrower', 'Borrower'), ('system', 'System')], max_length=12),
        ),
    ]
