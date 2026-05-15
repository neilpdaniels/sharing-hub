from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0015_registrationverification_avatar_more_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_age_vibe',
            field=models.CharField(blank=True, default='3', max_length=2),
        ),
    ]
