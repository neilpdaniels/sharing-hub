from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0030_product_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderimage',
            name='processing_error',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='orderimage',
            name='processing_status',
            field=models.CharField(
                choices=[
                    ('processing', 'Processing'),
                    ('ready', 'Ready'),
                    ('failed', 'Failed'),
                ],
                db_index=True,
                default='ready',
                max_length=12,
            ),
        ),
    ]
