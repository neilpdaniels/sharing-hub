from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0029_disputecase'),
    ]

    operations = [
        migrations.AddField(
            model_name='disputecase',
            name='borrower_final_statement_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='disputecase',
            name='lender_final_statement_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
