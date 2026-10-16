from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('navigation', '0010_catalogueproductreview_and_more')]
    operations = [
        migrations.AddField(
            model_name='catalogueproductrecommendation',
            name='recommended_action',
            field=models.TextField(blank=True, default=''),
        ),
    ]
