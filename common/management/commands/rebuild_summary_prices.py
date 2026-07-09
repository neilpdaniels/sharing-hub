from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from common.models import BestPricedForCategory, BestPricedForProduct, Category, Order, System
from common.tasks import updateSummaryPrices


class Command(BaseCommand):
    help = 'Rebuild derived best-price summary tables from existing orders.'

    def handle(self, *args, **options):
        created_products = 0
        created_categories = 0
        processed_orders = 0

        with db_transaction.atomic():
            for category in Category.objects.all():
                _, created = BestPricedForCategory.objects.get_or_create(category_id=category)
                if created:
                    created_categories += 1

            for category in Category.objects.prefetch_related('product_set').all():
                for product in category.product_set.all():
                    _, created = BestPricedForProduct.objects.get_or_create(product=product)
                    if created:
                        created_products += 1

            System.objects.update_or_create(
                name='summary_price_update_running',
                defaults={'value': 'True'},
            )

            for order in Order.objects.select_related('product').order_by('id'):
                updateSummaryPrices(order.pk)
                processed_orders += 1

            System.objects.update_or_create(
                name='summary_price_update_running',
                defaults={'value': 'False'},
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Summary price rebuild complete: '
                f'{created_categories} category cache rows created, '
                f'{created_products} product cache rows created, '
                f'{processed_orders} orders processed.'
            )
        )
