# Generated manually for the listing-specific title field.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0033_moderationreport_anonymous_reporter'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='listing_title',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='historicalorder',
            name='listing_title',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
