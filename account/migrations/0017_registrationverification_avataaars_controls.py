from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0016_registrationverification_avatar_age_vibe'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_accessories',
            field=models.CharField(blank=True, default='round', max_length=20),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_clothing',
            field=models.CharField(blank=True, default='hoodie', max_length=30),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_eyes',
            field=models.CharField(blank=True, default='default', max_length=20),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_facial_hair_color',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_mouth',
            field=models.CharField(blank=True, default='smile', max_length=20),
        ),
    ]
