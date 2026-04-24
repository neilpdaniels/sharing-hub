
from django.utils.text import slugify
import logging 
import common.static_load.static_load_categories as static_load_categories

def initialise_static():
    logging.info("starting data migration")
    static_load_categories.initialise_top_categories()
    logging.info("finished data migration")