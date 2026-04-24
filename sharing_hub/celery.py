import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "sharing_hub.settings.local"
)

app = Celery('sharing_hub')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

minutes_between_scrapes = 23
app.conf.beat_schedule  = {
    # all orders are set to expire at :59 seconds so we'll cron the expiry to work at 00:
    'add-task-order-expiry' : {
        'task': 'transaction.tasks.expireOrders',
        'schedule' : crontab(minute="*") # 5 # seconds - must be an integer
    },
    # 'add-task-kitco-gold-am': {
    #     'task': 'reference_price.tasks.scrapeKitcoGoldPrice',
    #     'schedule': crontab(minute='35,45,59', hour='10', day_of_week='0-6'),
    #     # 'args': (*args)
    # },
    # 'add-task-kitco-gold-pm': {
    #     'task': 'reference_price.tasks.scrapeKitcoGoldPrice',
    #     'schedule': crontab(minute='5,15,30', hour='14,15', day_of_week='0-6'),
    #     # 'args': (*args)
    # },
    # # TODO : Review Frequency pre golive
    # 'add-task-scrapeFXCombos': {
    #     'task': 'reference_price.tasks.scrapeFXCombos',
    #     'schedule': crontab(minute='10', hour='10', day_of_week='1-5'),
    #     # 'args': (*args)
    # },
    # 'add-task-intialise_scrape': {
    #     'task': 'quotes.tasks.intialise_scrape',
    #     'schedule': (minutes_between_scrapes*60),
    #     'args': ([minutes_between_scrapes])
    # },
    # 'add-task-scrape_thegoldbullion': {
    #     'task': 'quotes.tasks.scrape_thegoldbullion',
    #     'schedule': 15000.0 # seconds - not sure why set at 10 days
    # },
    
}

