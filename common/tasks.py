
from celery import shared_task
import logging 
import time
from django.shortcuts import get_object_or_404
from celery.utils.log import get_task_logger
import operator
import common.static_load.static_base

logger = get_task_logger(__name__)
 
def getCurrentBestPricedBids(item, count):
    from common.models import Category, Product, Order

    toReturn = []
    if isinstance(item, Product):
        logger.debug("Product")
        # get highest price of non expired buy orders 
        toReturn = item.order_set.filter(
            status=Order.ACTIVE,
            direction=Order.WANTED,
            quantity__gte=1,
        ).order_by('-price')[:count]

    elif isinstance(item, Category):
        logger.debug("Category")

        # add all to results, sort it and slice off top "count"
        # lazy, but let's see how efficient it is
        results = []

        # get highest price of best bid prices of member products and categories
        # select related, bring back in one query
        child_categories = Category.objects.all().filter(parent_category=item)
        for cat in child_categories :
            categoryBest = cat.best_prices.first()
            if categoryBest is not None:
                if categoryBest.bestPricedBid is not None:
                    results.append((categoryBest.bestPricedBid.price,categoryBest.bestPricedBid))
                if categoryBest.bestPricedBid2 is not None:
                    results.append((categoryBest.bestPricedBid2.price,categoryBest.bestPricedBid2))
                if categoryBest.bestPricedBid3 is not None:
                    results.append((categoryBest.bestPricedBid3.price,categoryBest.bestPricedBid3))
                if categoryBest.bestPricedBid4 is not None:
                    results.append((categoryBest.bestPricedBid4.price,categoryBest.bestPricedBid4))
                if categoryBest.bestPricedBid5 is not None:
                    results.append((categoryBest.bestPricedBid5.price,categoryBest.bestPricedBid5))
        
        child_products = item.product_set.all()
        child_products = child_products.filter(best_prices__numberActiveOrders__gt=0)
        for product in child_products :
            productBest = product.best_prices.first()
            if productBest is not None:
                if productBest.bestPricedBid is not None:
                    results.append((productBest.bestPricedBid.price,productBest.bestPricedBid))
                if productBest.bestPricedBid2 is not None:
                    results.append((productBest.bestPricedBid2.price,productBest.bestPricedBid2))
                if productBest.bestPricedBid3 is not None:
                    results.append((productBest.bestPricedBid3.price,productBest.bestPricedBid3))
                if productBest.bestPricedBid4 is not None:
                    results.append((productBest.bestPricedBid4.price,productBest.bestPricedBid4))
                if productBest.bestPricedBid5 is not None:
                    results.append((productBest.bestPricedBid5.price,productBest.bestPricedBid5))
            
        # filter out Nones
        # sort and select top 5        
        list(filter(None.__ne__, results))
        if len(results) > 0:
            results.sort(key = operator.itemgetter(0), reverse=True)
            for r in results:
                toReturn.append(r[1])
    return toReturn[:count]

def getCurrentBestPricedOffers(item, count):
    from common.models import Category, Product, Order

    toReturn = []
    if isinstance(item, Product):
        logger.debug("Product")
        # get highest price of non expired buy orders 
        toReturn = item.order_set.filter(
            status=Order.ACTIVE,
            direction=Order.TO_LET,
            quantity__gte=1,
        ).order_by('price')[:count]

    elif isinstance(item, Category):
        logger.debug("Category")

        # add all to results, sort it and slice off top "count"
        # lazy, but let's see how efficient it is
        results = []

        # get highest price of best offer prices of member products and categories
        # select related, bring back in one query
        child_categories = Category.objects.all().filter(parent_category=item)
        for cat in child_categories :
            categoryBest = cat.best_prices.first()
            if categoryBest is not None:
                if categoryBest.bestPricedOffer is not None:
                    results.append((categoryBest.bestPricedOffer.price,categoryBest.bestPricedOffer))
                if categoryBest.bestPricedOffer2 is not None:
                    results.append((categoryBest.bestPricedOffer2.price,categoryBest.bestPricedOffer2))
                if categoryBest.bestPricedOffer3 is not None:
                    results.append((categoryBest.bestPricedOffer3.price,categoryBest.bestPricedOffer3))
                if categoryBest.bestPricedOffer4 is not None:
                    results.append((categoryBest.bestPricedOffer4.price,categoryBest.bestPricedOffer4))
                if categoryBest.bestPricedOffer5 is not None:
                    results.append((categoryBest.bestPricedOffer5.price,categoryBest.bestPricedOffer5))
        
        child_products = item.product_set.all()
        child_products = child_products.filter(best_prices__numberActiveOrders__gt=0)
        for product in child_products :
            productBest = product.best_prices.first()
            if productBest is not None:
                if productBest.bestPricedOffer is not None:
                    results.append((productBest.bestPricedOffer.price,productBest.bestPricedOffer))
                if productBest.bestPricedOffer2 is not None:
                    results.append((productBest.bestPricedOffer2.price,productBest.bestPricedOffer2))
                if productBest.bestPricedOffer3 is not None:
                    results.append((productBest.bestPricedOffer3.price,productBest.bestPricedOffer3))
                if productBest.bestPricedOffer4 is not None:
                    results.append((productBest.bestPricedOffer4.price,productBest.bestPricedOffer4))
                if productBest.bestPricedOffer5 is not None:
                    results.append((productBest.bestPricedOffer5.price,productBest.bestPricedOffer5))
            
        # filter out Nones
        # sort and select top 5        
        list(filter(None.__ne__, results))
        if len(results) > 0:
            results.sort(key = operator.itemgetter(0))
            for r in results:
                toReturn.append(r[1])
    return toReturn[:count]

def checkCategoryBestPriceBid(category, order):
    from common.models import BestPricedForProduct, BestPricedForCategory
    from common.models import Category, Product, Order

    logger.debug(category.slug)
    best_prices = BestPricedForCategory.objects.get(category_id = category)
    currentBestOrders = [best_prices.bestPricedBid,best_prices.bestPricedBid2,best_prices.bestPricedBid3,best_prices.bestPricedBid4,best_prices.bestPricedBid5]
    new_top_five_bid_prices = getCurrentBestPricedBids(category, 5)
    toRecurse = False
    if order in currentBestOrders:
        toRecurse = True
    if order in new_top_five_bid_prices:
        toRecurse = True
    if toRecurse:

        if len(new_top_five_bid_prices) > 0:
            best_prices.bestPricedBid = new_top_five_bid_prices[0]
        else:
            best_prices.bestPricedBid = None

        if len(new_top_five_bid_prices) > 1:
            best_prices.bestPricedBid2 = new_top_five_bid_prices[1]
        else:
            best_prices.bestPricedBid2 = None

        if len(new_top_five_bid_prices) > 2:
            best_prices.bestPricedBid3 = new_top_five_bid_prices[2]
        else:
            best_prices.bestPricedBid3 = None

        if len(new_top_five_bid_prices) > 3:
            best_prices.bestPricedBid4 = new_top_five_bid_prices[3]
        else:
            best_prices.bestPricedBid4 = None

        if len(new_top_five_bid_prices) > 4:
            best_prices.bestPricedBid5 = new_top_five_bid_prices[4]
        else:
            best_prices.bestPricedBid5 = None
        best_prices.save()
        if category.parent_category is not None:
            checkCategoryBestPriceBid(category.parent_category, order)

    
def checkCategoryBestPriceOffer(category, order):
    from common.models import BestPricedForProduct, BestPricedForCategory
    from common.models import Category, Product, Order

    best_prices = BestPricedForCategory.objects.get(category_id = category)
    currentBestOrders = [best_prices.bestPricedOffer,best_prices.bestPricedOffer2,best_prices.bestPricedOffer3,best_prices.bestPricedOffer4,best_prices.bestPricedOffer5]

    new_top_five_offer_prices = getCurrentBestPricedOffers(category,5)

    toRecurse = False
    if order in currentBestOrders:
        toRecurse = True
    if order in new_top_five_offer_prices:
        toRecurse = True
    if toRecurse:
        if len(new_top_five_offer_prices) > 0:
            best_prices.bestPricedOffer = new_top_five_offer_prices[0]
        else: 
            best_prices.bestPricedOffer = None
        if len(new_top_five_offer_prices) > 1:
            best_prices.bestPricedOffer2 = new_top_five_offer_prices[1]
        else: 
            best_prices.bestPricedOffer2 = None
        if len(new_top_five_offer_prices) > 2:
            best_prices.bestPricedOffer3 = new_top_five_offer_prices[2]
        else: 
            best_prices.bestPricedOffer3 = None
        if len(new_top_five_offer_prices) > 3:
            best_prices.bestPricedOffer4 = new_top_five_offer_prices[3]
        else: 
            best_prices.bestPricedOffer4 = None
        if len(new_top_five_offer_prices) > 4:
            best_prices.bestPricedOffer5 = new_top_five_offer_prices[4]
        else: 
            best_prices.bestPricedOffer5 = None
        best_prices.save()
        if category.parent_category is not None:
            checkCategoryBestPriceOffer(category.parent_category
            , order)


@shared_task
def updateSummaryPrices( order_pk ):
    # unpleasant:
    from common.models import BestPricedForProduct, BestPricedForCategory
    from common.models import Category, Product, Order, System

    logger.debug("Updating summary prices for {}".format(order_pk))
    order = get_object_or_404(Order, pk=order_pk)
    updateRunning, created = System.objects.get_or_create(name="summary_price_update_running")
    updateRunning.value = "True"
    updateRunning.save()

    best_prices = BestPricedForProduct.objects.get(product=order.product)
    currentBestBids = [best_prices.bestPricedBid,best_prices.bestPricedBid2,best_prices.bestPricedBid3,best_prices.bestPricedBid4,best_prices.bestPricedBid5]
    currentBestOffers = [best_prices.bestPricedOffer,best_prices.bestPricedOffer2,best_prices.bestPricedOffer3,best_prices.bestPricedOffer4,best_prices.bestPricedOffer5]

    if order.direction == Order.WANTED:
        logger.debug(order.product.category_id.slug)
        logger.debug(order.product.name)
        new_top_five_bid_prices = getCurrentBestPricedBids(order.product, 5)
        toRecurse = False
        if order in currentBestBids:
            toRecurse = True
        if order in new_top_five_bid_prices:
            toRecurse = True
        if toRecurse:
            if len(new_top_five_bid_prices) > 0:
                best_prices.bestPricedBid = new_top_five_bid_prices[0]
            else:
                best_prices.bestPricedBid = None

            if len(new_top_five_bid_prices) > 1:
                best_prices.bestPricedBid2 = new_top_five_bid_prices[1]
            else:
                best_prices.bestPricedBid2 = None

            if len(new_top_five_bid_prices) > 2:
                best_prices.bestPricedBid3 = new_top_five_bid_prices[2]
            else:
                best_prices.bestPricedBid3 = None

            if len(new_top_five_bid_prices) > 3:
                best_prices.bestPricedBid4 = new_top_five_bid_prices[3]
            else:
                best_prices.bestPricedBid4 = None

            if len(new_top_five_bid_prices) > 4:
                best_prices.bestPricedBid5 = new_top_five_bid_prices[4]
            else:
                best_prices.bestPricedBid5 = None

            # update number of active orders
            best_prices.numberActiveOrders = order.product.order_set.filter(status='A').count()   
            best_prices.save()

            checkCategoryBestPriceBid(order.product.category_id, order)

    elif order.direction == Order.TO_LET:
        new_top_five_offer_prices = getCurrentBestPricedOffers(order.product, 5)
        toRecurse = False
        if order in currentBestOffers:
            toRecurse = True
        if order in new_top_five_offer_prices:
            toRecurse = True
        if toRecurse:
            if len(new_top_five_offer_prices) > 0:
                best_prices.bestPricedOffer = new_top_five_offer_prices[0]
            else: 
                best_prices.bestPricedOffer = None

            if len(new_top_five_offer_prices) > 1:
                best_prices.bestPricedOffer2 = new_top_five_offer_prices[1]
            else: 
                best_prices.bestPricedOffer2 = None

            if len(new_top_five_offer_prices) > 2:
                best_prices.bestPricedOffer3 = new_top_five_offer_prices[2]
            else: 
                best_prices.bestPricedOffer3 = None

            if len(new_top_five_offer_prices) > 3:
                best_prices.bestPricedOffer4 = new_top_five_offer_prices[3]
            else: 
                best_prices.bestPricedOffer4 = None

            if len(new_top_five_offer_prices) > 4:
                best_prices.bestPricedOffer5 = new_top_five_offer_prices[4]
            else: 
                best_prices.bestPricedOffer5 = None

            # update number of active orders
            best_prices.numberActiveOrders = order.product.order_set.filter(status='A').count()   

            best_prices.save()
            checkCategoryBestPriceOffer(order.product.category_id, order)

    updateRunning.value = "False"
    updateRunning.save()


# migration to top 5 for each product category
# keep logic simple here
# if order is in top 5 already, or in new top 5, apply new top 5 and recurse to parent
# if not, stop

@shared_task
def runStaticMigration():
    common.static_load.static_base.initialise_static()


@shared_task
def listEmptyCategories(  ):
    # from common.models import BestPricedForProduct, BestPricedForCategory
    from common.models import Category, Product, Order, System
    categories = Category.objects.all()
    for cat in categories:
        # child_categories = cat.parent_category_set.all()
        child_cat_count = cat.category_set.all().count()
        child_prod_count = cat.product_set.all().count()
        if child_prod_count == 0 and child_cat_count == 0:
            logging.error("{} : {} , {}".format(cat.title, child_cat_count, child_prod_count))
            # cat.delete()