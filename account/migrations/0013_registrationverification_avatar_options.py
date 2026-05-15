from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0012_registrationverification_avatar_preset'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_gender_vibe',
            field=models.CharField(blank=True, default='neutral', max_length=20),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_hair_color',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_style',
            field=models.CharField(blank=True, default='auto', max_length=40),
        ),
    ]
