from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0015_category_risk_rating_product_risk_rating'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoryAttribute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(help_text='Display order for the attribute (starts at 1)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(50)])),
                ('name', models.CharField(blank=True, max_length=200, null=True)),
                ('sortable', models.BooleanField(default=False)),
                ('filterable', models.BooleanField(default=False)),
                ('default_filtered_value', models.CharField(blank=True, max_length=200, null=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_attributes', to='common.category')),
            ],
            options={
                'ordering': ('order',),
                'unique_together': {('category', 'order')},
            },
        ),
    ]
