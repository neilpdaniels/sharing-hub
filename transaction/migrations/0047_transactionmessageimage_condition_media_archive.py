from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('transaction', '0046_historicaltransactionmessage_moderation_hidden')]

    operations = [
        migrations.AddField(
            model_name='transactionmessageimage',
            name='archived_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='archive_expires_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='transactionmessageimage',
            name='archive_manifest',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
