from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0010_historicalorder_let_visibility'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderblockeddate',
            name='reason',
            field=models.CharField(
                choices=[
                    ('M', 'Manual'),
                    ('B', 'Booked'),
                    ('H', 'Unavailable for collection/drop-off'),
                ],
                default='M',
                max_length=1,
            ),
        ),
    ]
