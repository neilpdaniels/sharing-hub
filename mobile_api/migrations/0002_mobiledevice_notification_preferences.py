from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobile_api', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobiledevice',
            name='notify_in_app_alerts',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='mobiledevice',
            name='notify_transaction_enquiry',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='mobiledevice',
            name='notify_transaction_messages',
            field=models.BooleanField(default=True),
        ),
    ]
