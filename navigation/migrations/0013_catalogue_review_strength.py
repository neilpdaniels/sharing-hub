from django.db import migrations, models


STRENGTH_CHOICES = [
    ('LIGHT', 'Light — obvious cleanup only'),
    ('MEDIUM', 'Medium — practical improvement'),
    ('HEAVY', 'Heavy — proactive reorganisation'),
]


class Migration(migrations.Migration):
    dependencies = [('navigation', '0012_catalogueproductrecommendation_safe_application')]

    operations = [
        migrations.AddField(
            model_name='catalogueproductreview',
            name='review_strength',
            field=models.CharField(choices=STRENGTH_CHOICES, default='MEDIUM', max_length=8),
        ),
        migrations.AddField(
            model_name='categorytaxonomyreview',
            name='review_strength',
            field=models.CharField(choices=STRENGTH_CHOICES, default='MEDIUM', max_length=8),
        ),
    ]
