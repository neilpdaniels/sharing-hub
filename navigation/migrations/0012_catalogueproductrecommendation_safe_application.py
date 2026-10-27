from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('navigation', '0011_catalogueproductrecommendation_recommended_action')]

    operations = [
        migrations.AddField(
            model_name='catalogueproductrecommendation',
            name='application_result',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='catalogueproductrecommendation',
            name='proposed_action',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='catalogueproductrecommendation',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending human review'),
                    ('REVIEWED', 'Reviewed without change'),
                    ('REJECTED', 'Rejected'),
                    ('APPLIED', 'Applied safely'),
                ],
                db_index=True,
                default='PENDING',
                max_length=12,
            ),
        ),
    ]
