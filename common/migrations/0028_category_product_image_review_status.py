from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0027_categoryattribute_value_source_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='image_review_notes',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='category',
            name='image_review_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('awaiting_review', 'Awaiting review'),
                    ('reviewed', 'Reviewed'),
                    ('skipped', 'Skipped'),
                    ('done_elsewhere', 'Done elsewhere'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='category',
            name='image_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='image_review_notes',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='product',
            name='image_review_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('awaiting_review', 'Awaiting review'),
                    ('reviewed', 'Reviewed'),
                    ('skipped', 'Skipped'),
                    ('done_elsewhere', 'Done elsewhere'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='image_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
