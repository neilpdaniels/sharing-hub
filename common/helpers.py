import os
import uuid
from django.utils.deconstruct import deconstructible
from itertools import chain
from datetime import datetime

def getBestActiveOrderByPrice(product,direction):
    toReturn = None
    if direction=='B':
        toReturn = product.order_set.filter(status='A', direction='S').order_by('price').first()
    else:
        toReturn = product.order_set.filter(status='A', direction='B').order_by('-price').first()
    return toReturn

def getBestXActiveOrdersByPrice(product,direction,count):
    toReturn = None
    if direction=='B':
        toReturn = product.order_set.filter(status='A', direction='S').order_by('price')[:count]
    else:
        toReturn = product.order_set.filter(status='A', direction='B').order_by('-price')[:count]
    return toReturn

def getAllActiveOrdersByPrice(product,direction):
    toReturn = None
    if direction=='B':
        toReturn = product.order_set.filter(status='A', direction='S').order_by('price')
    else:
        toReturn = product.order_set.filter(status='A', direction='B').order_by('-price')
    return toReturn

# recursively looks for all products
def getAllProductsUnderCategory(cat):
    toReturn = list(cat.product_set.all())
    childCategories = cat.category_set.all().iterator()
    for child in childCategories:
        toReturn = list(chain(toReturn, getAllProductsUnderCategory(child)))
    return toReturn

@deconstructible
class RandomFileName(object):
    def __init__(self, path):
        self.path = os.path.join(path, "%s%s")

    def __call__(self, _, filename):
        # @note It's up to the validators to check if it's the correct file type in name or if one even exist.
        extension = os.path.splitext(filename)[1]
        return self.path % (uuid.uuid4(), extension)