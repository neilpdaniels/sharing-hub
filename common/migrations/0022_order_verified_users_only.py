from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0021_historicalorder_collection_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='verified_users_only',
            field=models.BooleanField(
                default=False,
                help_text='Only users who have completed Stripe identity verification can enquire on this listing.',
            ),
        ),
    ]
