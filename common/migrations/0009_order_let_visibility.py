from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0008_orderimage_is_main'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='let_visibility',
            field=models.CharField(
                choices=[
                    ('FRIENDS', 'Let to friends only'),
                    ('PUBLIC', 'Let to public only'),
                    ('BOTH', 'Let to both'),
                ],
                db_index=True,
                default='BOTH',
                help_text='Who can see and rent this listing',
                max_length=8,
            ),
        ),
    ]
