from django.apps import AppConfig

class ReferencePriceConfig(AppConfig):
    name = 'reference_price'

    def ready(self):
        import reference_price.signals  # noqa