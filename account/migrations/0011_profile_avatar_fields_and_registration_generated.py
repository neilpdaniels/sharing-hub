# Generated manually for avatar generation support

import common.helpers
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0010_registrationverification_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='avatar_provider',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='profile',
            name='image_generated',
            field=models.ImageField(blank=True, upload_to=common.helpers.RandomFileName('users/generated/')),
        ),
        migrations.AddField(
            model_name='profile',
            name='image_original',
            field=models.ImageField(blank=True, upload_to=common.helpers.RandomFileName('users/raw/')),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_generation_consent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='generated_image',
            field=models.ImageField(blank=True, upload_to=common.helpers.RandomFileName('users/generated/')),
        ),
    ]
