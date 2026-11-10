from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0035_catalogimagegeneration_catalogimagecandidate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catalogimagegeneration',
            name='model',
            field=models.CharField(default='gpt-image-2.5-flare', max_length=80),
        ),
    ]
