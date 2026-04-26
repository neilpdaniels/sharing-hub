from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_profile_mobile_and_registrationverification'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='house_name_number',
            field=models.CharField(blank=True, default='', max_length=255),
            preserve_default=False,
        ),
    ]
