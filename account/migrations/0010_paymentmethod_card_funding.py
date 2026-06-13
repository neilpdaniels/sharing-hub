from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0009_remove_profile_stripe_identity_verification_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentmethod',
            name='card_funding',
            field=models.CharField(blank=True, default='', help_text='Card funding type from Stripe (credit, debit, prepaid, etc.)', max_length=20),
        ),
    ]
