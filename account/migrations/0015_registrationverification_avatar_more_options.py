from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0014_registrationverification_avatar_skin_tone'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_facial_hair',
            field=models.PositiveSmallIntegerField(default=25),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_glasses',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_hair_length',
            field=models.CharField(blank=True, default='any', max_length=10),
        ),
    ]
