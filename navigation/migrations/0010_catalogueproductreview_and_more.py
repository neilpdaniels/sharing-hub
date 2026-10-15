from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('navigation', '0009_categorysuggestion_product_proposals')]
    operations = [
        migrations.CreateModel(name='CatalogueProductReview', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('status', models.CharField(choices=[('QUEUED', 'Queued'), ('RUNNING', 'Running'), ('READY', 'Ready for human review'), ('FAILED', 'Failed')], db_index=True, default='QUEUED', max_length=12)),
            ('snapshot', models.JSONField(blank=True, default=dict)), ('llm_analysis', models.JSONField(blank=True, default=dict)),
            ('error', models.TextField(blank=True, default='')), ('started_at', models.DateTimeField(blank=True, null=True)),
            ('completed_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel(name='CatalogueProductRecommendation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('position', models.PositiveSmallIntegerField()),
            ('recommendation_type', models.CharField(choices=[('DUPLICATE', 'Possible duplicate / consolidate'), ('LOW_VALUE', 'Low-value / consumer-fit review'), ('KEEP', 'Keep — specialist exception')], max_length=16)),
            ('title', models.CharField(max_length=255)), ('rationale', models.TextField()),
            ('evidence', models.JSONField(blank=True, default=list)), ('affected_product_ids', models.JSONField(blank=True, default=list)),
            ('consumer_assessment', models.JSONField(blank=True, default=dict)),
            ('status', models.CharField(choices=[('PENDING', 'Pending human review'), ('REVIEWED', 'Reviewed'), ('REJECTED', 'Rejected')], db_index=True, default='PENDING', max_length=12)),
            ('admin_notes', models.TextField(blank=True, default='')), ('reviewed_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommendations', to='navigation.catalogueproductreview')),
            ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['review', 'position'], 'unique_together': {('review', 'position')}}),
    ]
