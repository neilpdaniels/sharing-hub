from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0036_alter_catalogimagegeneration_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='catalogimagecandidate',
            name='is_dismissed',
            field=models.BooleanField(default=False),
        ),
    ]
