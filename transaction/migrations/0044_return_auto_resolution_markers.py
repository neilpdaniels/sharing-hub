from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0043_transaction_lifecycle_email_markers'),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=model_name,
                name=field_name,
                field=models.DateTimeField(blank=True, null=True),
            )
            for model_name in ('transaction', 'historicaltransaction')
            for field_name in (
                'return_auto_resolution_eod_alert_at',
                'return_auto_resolved_at',
            )
        ],
    ]
