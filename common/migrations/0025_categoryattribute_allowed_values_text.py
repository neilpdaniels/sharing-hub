from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0024_sitefailure'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoryattribute',
            name='allowed_values_text',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional fixed choices, one per line. Leave blank to allow free text.',
            ),
        ),
    ]
