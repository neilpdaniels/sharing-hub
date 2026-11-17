from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('navigation', '0018_catalogueproductreview_scope_category'),
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
                    ('PRODUCT_STRUCTURE', 'Create or split product templates (manual plan)'),
                    ('KEEP', 'Keep — specialist exception'),
                ],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='categorytaxonomyreview',
            name='operator_instruction',
            field=models.TextField(blank=True, default='', help_text='Optional staff brief that directs this review. It never makes changes automatically.'),
        ),
        migrations.AddField(
            model_name='catalogueproductreview',
            name='operator_instruction',
            field=models.TextField(blank=True, default='', help_text='Optional staff brief that directs this review. It never makes changes automatically.'),
        ),
        migrations.AddField(
            model_name='cataloguecleanupreview',
            name='operator_instruction',
            field=models.TextField(blank=True, default='', help_text='Optional staff brief that directs both parts of this review. It never makes changes automatically.'),
        ),
        migrations.AddField(
            model_name='cataloguecleanupreview',
            name='scope_category',
            field=models.ForeignKey(blank=True, help_text='Optional category whose complete subtree is reviewed. Leave blank for the whole catalogue.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cleanup_reviews', to='common.category'),
        ),
    ]
