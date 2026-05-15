from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0017_registrationverification_avataaars_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_clothes_color',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]
