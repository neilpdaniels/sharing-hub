from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductListingRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_slug', models.SlugField(blank=True, max_length=120)),
                ('category_title', models.CharField(blank=True, max_length=255)),
                ('product_name', models.CharField(max_length=255)),
                ('request_details', models.TextField()),
                ('status', models.CharField(choices=[('NEW', 'New'), ('REVIEWED', 'Reviewed'), ('FULFILLED', 'Fulfilled')], default='NEW', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='product_listing_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
