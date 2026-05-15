# Generated manually for sample avatar preset support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0011_profile_avatar_fields_and_registration_generated'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationverification',
            name='avatar_preset',
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
