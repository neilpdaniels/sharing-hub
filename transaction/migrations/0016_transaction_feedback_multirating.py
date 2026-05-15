from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0015_transaction_deposit_negotiation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionfeedback',
            name='communication_rating',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name='transactionfeedback',
            name='delivery_return_rating',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name='transactionfeedback',
            name='overall_rating',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AlterField(
            model_name='transactionfeedback',
            name='rating',
            field=models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddConstraint(
            model_name='transactionfeedback',
            constraint=models.UniqueConstraint(fields=('transaction', 'left_by', 'left_for'), name='uniq_feedback_per_direction_per_transaction'),
        ),
    ]
