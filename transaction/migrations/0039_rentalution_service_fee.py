from django.db import migrations


def rename_and_standardize_service_fee(apps, schema_editor):
    TransactionFee = apps.get_model('common', 'TransactionFee')
    TransactionFeeBand = apps.get_model('common', 'TransactionFeeBand')

    fee = TransactionFee.objects.filter(name__in=('Rentalution service fee', 'Rentalution fee')).order_by('id').first()
    if fee is None:
        return

    fee.name = 'Rentalution service fee'
    fee.slug = 'rentalution_service_fee'
    fee.save(update_fields=['name', 'slug'])
    TransactionFeeBand.objects.filter(transaction_fee=fee).delete()
    TransactionFeeBand.objects.create(
        transaction_fee=fee,
        price=10,
        max_price=999999,
        price_style='P',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0038_transactionmessageimage_preview_status_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_and_standardize_service_fee, migrations.RunPython.noop),
    ]
