from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0031_orderimage_processing_status'),
        ('navigation', '0008_categorytaxonomyrecommendation_attribute_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorysuggestion',
            name='proposal_kind',
            field=models.CharField(
                choices=[('PRODUCT', 'Product in an existing category'), ('CATEGORY', 'New category')],
                db_index=True,
                default='CATEGORY',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='categorysuggestion',
            name='published_product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='published_from_suggestions',
                to='common.product',
            ),
        ),
    ]
