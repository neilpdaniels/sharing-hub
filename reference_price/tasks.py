from celery import shared_task
from bs4 import BeautifulSoup
# import urllib
from six.moves.urllib.request import urlopen
import logging 
from .models import ReferencePrice
import json
from django.template.defaultfilters import slugify

# @app.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     # Calls test('hello') every 10 seconds.
#     sender.add_periodic_task(10.0, test.s('hello'), name='add every 10')

#     # Calls test('world') every 30 seconds
#     sender.add_periodic_task(30.0, test.s('world'), expires=10)

#     # Executes every Monday morning at 7:30 a.m.
#     sender.add_periodic_task(
#         crontab(hour=7, minute=30, day_of_week=1),
#         test.s('Happy Mondays!'),
#     )

@shared_task
def scrapeFXCombos():
    logging.error("Running scraping FX combos")
    url = "http://www.apilayer.net/api/live?access_key=27ebed219778fe360507b41115fe8f6e"
    res = urlopen(url)
    resjson = json.loads(res.read())
    usdgbp = 1 / resjson['quotes']['USDGBP'] # 0.77 -> 1.3
    for quoteKey, quoteVal in resjson['quotes'].items():
        gbpPrice = quoteVal * usdgbp
            
        try:
            gbpRef = "GBP" + quoteKey[3:]
            gbpRefPx = ReferencePrice.objects.get(title=gbpRef)
            gbpRefPx.price = gbpPrice
            gbpRefPx.gbp_price = gbpPrice
            gbpRefPx.save()
        except ReferencePrice.DoesNotExist:
            gbpPrice = quoteVal 
            gbpRef = "GBP" + quoteKey[3:]
            gbpRefPx = ReferencePrice(title=gbpRef, slug=gbpRef, price=gbpPrice, gbp_price=gbpPrice, currency="GBP")
            gbpRefPx.save()

        try:
            usdRefPx = ReferencePrice.objects.get(title=quoteKey)
            usdRefPx.price = quoteVal
            usdRefPx.gbp_price = gbpPrice
            usdRefPx.save()
        except ReferencePrice.DoesNotExist:
            usdRefPx = ReferencePrice(title=quoteKey, slug=quoteKey, price=quoteVal, gbp_price=gbpPrice, currency="USD")
            usdRefPx.save()

@shared_task
def scrapeKitcoGoldPrice():
    # TODO: make dynamic?
    url = "http://www.kitco.com/gold.londonfix.html"
    soup = BeautifulSoup(urlopen(url), "lxml")

    tolerance = 85

    # gold
    am_price = soup.find("tr", { "class" : "even"}).find("td", {"class" : "am" }).text
    pm_price = soup.find("tr", { "class" : "even"}).find("td", {"class" : "pm" }).text
    title_ ="Gold price 1Oz USD"
    try:
        ref_px = ReferencePrice.objects.get(slug=slugify(title_))
    except ReferencePrice.DoesNotExist:
        ref_px = ReferencePrice(slug=slugify(title_), title=title_, currency="USD", default_for_metal="gold")

    price = float(am_price)
    try:
        price = float(pm_price)
    except (ValueError, TypeError):
        price = float(am_price)

    continue_ = False
    if ref_px.price is None:
        continue_ = True
    else:
        pct = (min(price, ref_px.price) / max(price, ref_px.price))*100
        if pct > tolerance:
            continue_ = True

    if continue_:
        # TODO: convert to GBP  
        usdgbp = ReferencePrice.objects.get(slug='usdgbp')
        ref_px.gbp_price = price * usdgbp.price
        ref_px.price = price
        ref_px.save()
    else:
        logging.error("GOLD: price deviation too high {} -> {}".format(ref_px.price, price))    

    # silver
    price = soup.find("tr", { "class" : "even"}).find("td", {"class" : "silver" }).text
    title_ ="Silver price 1Oz USD"
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0
    try:
        ref_px = ReferencePrice.objects.get(slug=slugify(title_))
    except ReferencePrice.DoesNotExist:
        ref_px = ReferencePrice(slug=slugify(title_), title=title_, currency="USD", default_for_metal="silver")

    continue_ = False
    if ref_px.price is None:
        continue_ = True
    else:
        pct = (min(price, ref_px.price) / max(price, ref_px.price))*100
        if pct > tolerance:
            continue_ = True

    if continue_:
        # TODO: convert to GBP  
        usdgbp = ReferencePrice.objects.get(slug='usdgbp')
        ref_px.gbp_price = price * usdgbp.price
        ref_px.price = price
        ref_px.save()
    else:
        logging.error("Silver: price deviation too high {} -> {}".format(ref_px.price, price))    

    # platinum
    am_price = soup.find("tr", { "class" : "even"}).findAll("td", {"class" : "am" })[1].text
    pm_price = soup.find("tr", { "class" : "even"}).findAll("td", {"class" : "pm" })[1].text
    title_ ="Platinum price 1Oz USD"
    try:
        ref_px = ReferencePrice.objects.get(slug=slugify(title_))
    except ReferencePrice.DoesNotExist:
        ref_px = ReferencePrice(slug=slugify(title_), title=title_, currency="USD", default_for_metal="platinum")

    price = float(am_price)
    try:
        price = float(pm_price)
    except (ValueError, TypeError):
        price = float(am_price)

    continue_ = False
    if ref_px.price is None:
        continue_ = True
    else:
        pct = (min(price, ref_px.price) / max(price, ref_px.price))*100
        if pct > tolerance:
            continue_ = True

    if continue_:
        # TODO: convert to GBP  
        usdgbp = ReferencePrice.objects.get(slug='usdgbp')
        ref_px.gbp_price = price * usdgbp.price
        ref_px.price = price
        ref_px.save()
    else:
        logging.error("Platinum: price deviation too high {} -> {}".format(ref_px.price, price))    


    # palladium
    am_price = soup.find("tr", { "class" : "even"}).findAll("td", {"class" : "am" })[2].text
    pm_price = soup.find("tr", { "class" : "even"}).findAll("td", {"class" : "pm" })[2].text

    title_ ="Palladium price 1Oz USD"
    try:
        ref_px = ReferencePrice.objects.get(slug=slugify(title_))
    except ReferencePrice.DoesNotExist:
        ref_px = ReferencePrice(slug=slugify(title_), title=title_, currency="USD", default_for_metal="palladium")

    price = float(am_price)
    try:
        price = float(pm_price)
    except (ValueError, TypeError):
        price = float(am_price)

    continue_ = False
    if ref_px.price is None:
        continue_ = True
    else:
        pct = (min(price, ref_px.price) / max(price, ref_px.price))*100
        if pct > tolerance:
            continue_ = True

    if continue_:
        # TODO: convert to GBP  
        usdgbp = ReferencePrice.objects.get(slug='usdgbp')
        ref_px.gbp_price = price * usdgbp.price
        ref_px.price = price
        ref_px.save()
    else:
        logging.error("Palladium: price deviation too high {} -> {}".format(ref_px.price, price))    

    