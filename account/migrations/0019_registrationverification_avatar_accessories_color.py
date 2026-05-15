from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0018_registrationverification_avatar_clothes_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_accessories_color',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]
