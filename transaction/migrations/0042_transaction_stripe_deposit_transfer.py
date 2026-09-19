from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('transaction', '0041_stripesettlement')]

    operations = [
        migrations.AddField(model_name='transaction', name='stripe_deposit_transfer_id', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='transaction', name='stripe_deposit_transfer_status', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='transaction', name='stripe_deposit_transfer_amount', field=models.FloatField(default=0)),
        migrations.AddField(model_name='historicaltransaction', name='stripe_deposit_transfer_id', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='historicaltransaction', name='stripe_deposit_transfer_status', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='historicaltransaction', name='stripe_deposit_transfer_amount', field=models.FloatField(default=0)),
    ]
