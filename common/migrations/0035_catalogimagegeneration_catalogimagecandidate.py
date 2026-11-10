from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import common.helpers


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0034_order_listing_title'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CatalogImageGeneration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt', models.TextField()),
                ('model', models.CharField(default='gpt-image-1', max_length=80)),
                ('quality', models.CharField(default='medium', max_length=20)),
                ('size', models.CharField(default='1024x1024', max_length=20)),
                ('requested_count', models.PositiveSmallIntegerField(default=2)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='image_generations', to='common.category')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='image_generations', to='common.product')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.CreateModel(
            name='CatalogImageCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to=common.helpers.RandomFileName('images/catalog-generated/'))),
                ('position', models.PositiveSmallIntegerField(default=1)),
                ('is_selected', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('generation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='candidates', to='common.catalogimagegeneration')),
            ],
            options={'ordering': ('generation', 'position', 'id'), 'unique_together': {('generation', 'position')}},
        ),
    ]
