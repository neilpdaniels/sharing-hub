from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0042_transaction_stripe_deposit_transfer'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltransaction',
            name='rental_ready_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='rental_day_reminder_sent_for',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaltransaction',
            name='return_day_reminder_sent_for',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='rental_ready_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='rental_day_reminder_sent_for',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='return_day_reminder_sent_for',
            field=models.DateField(blank=True, null=True),
        ),
    ]
