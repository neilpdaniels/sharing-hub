from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0013_registrationverification_avatar_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_skin_tone',
            field=models.CharField(blank=True, default='4', max_length=2),
        ),
    ]
