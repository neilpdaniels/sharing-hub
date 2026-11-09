from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('navigation', '0015_cataloguecleanupreview'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catalogueproductrecommendation',
            name='recommendation_type',
            field=models.CharField(
                choices=[
                    ('DUPLICATE', 'Possible duplicate / consolidate'),
                    ('LOW_VALUE', 'Low-value / consumer-fit review'),
                    ('LISTING_VARIANTS', 'Use one product type with listing variants'),
                    ('KEEP', 'Keep — specialist exception'),
                ],
                max_length=16,
            ),
        ),
    ]
