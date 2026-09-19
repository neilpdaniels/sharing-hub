import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('transaction', '0040_transaction_stripe_connect_settlement')]

    operations = [
        migrations.AlterField(
            model_name='transaction', name='rentalution_fee',
            field=models.FloatField(default=0, help_text='Computed Rentalution service fee charged for this transaction', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999999)]),
        ),
        migrations.AlterField(
            model_name='historicaltransaction', name='rentalution_fee',
            field=models.FloatField(default=0, help_text='Computed Rentalution service fee charged for this transaction', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999999)]),
        ),
        migrations.CreateModel(
            name='StripeSettlement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('rental', 'Rental proceeds'), ('deposit', 'Deposit award')], max_length=16)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='pending', max_length=16)),
                ('gross_amount', models.FloatField(default=0)), ('stripe_fee', models.FloatField(default=0)),
                ('net_transfer_amount', models.FloatField(default=0)), ('platform_shortfall', models.FloatField(default=0)),
                ('payment_intent_id', models.CharField(blank=True, max_length=120)), ('charge_id', models.CharField(blank=True, max_length=120)),
                ('balance_transaction_id', models.CharField(blank=True, max_length=120)), ('transfer_id', models.CharField(blank=True, max_length=120)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)), ('failure_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('transaction', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='stripe_settlements', to='transaction.transaction')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddConstraint(model_name='stripesettlement', constraint=models.UniqueConstraint(fields=('transaction', 'kind'), name='one_connect_settlement_per_kind')),
    ]
