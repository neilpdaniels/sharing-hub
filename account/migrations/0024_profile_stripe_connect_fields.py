from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('account', '0023_alter_paymentmethod_id_alter_profile_id_and_more')]

    operations = [
        migrations.AddField(model_name='profile', name='stripe_connect_account_id', field=models.CharField(blank=True, max_length=255, null=True, unique=True)),
        migrations.AddField(model_name='profile', name='stripe_connect_transfers_enabled', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='profile', name='stripe_connect_payouts_enabled', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='profile', name='stripe_connect_requirements', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='profile', name='stripe_connect_last_synced_at', field=models.DateTimeField(blank=True, null=True)),
    ]
