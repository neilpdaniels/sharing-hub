from datetime import datetime
import logging
import urllib.parse

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import cache_page
from haystack.forms import SearchForm
from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet

import common.helpers
from common.decorators import ajax_required
from common.geocoding import PostcodeGeocoder
from common.catalog_attributes import (
    apply_attribute_filters,
    attribute_sort_options,
    collect_attribute_filter_options,
    default_sort_value,
    field_name_for_definition,
    filterable_attribute_definitions,
    matches_attribute_sort,
    sortable_attribute_definitions,
)
from common.models import (
    BestPricedForCategory, BestPricedForProduct, Category, CategoryTag,
    FavouriteOrder, Order, Product, System,
)
from common.tasks import listEmptyCategories, runStaticMigration
from transaction.helpers import get_user_feedback_breakdown, get_user_feedback_breakdown_map
from transaction.models import Transaction

from ..forms import CategorySuggestionForm
from ..models import SearchHistory


logger = logging.getLogger(__name__)


def _get_homepage_categories(limit=12):
    return list(common.helpers.get_ordered_top_categories()[:limit])


def _get_homepage_popular_orders(request, limit=8):
    popular_orders = list(
        Order.objects.filter(status=Order.ACTIVE, direction=Order.TO_LET)
        .select_related('product', 'product__category_id', 'user')
        .prefetch_related('images')
        .annotate(favourite_count=Count('favourited_by', distinct=True))
        .order_by('-favourite_count', '-amended')[:limit * 4]
    )

    if not popular_orders:
        return []

    home_lat = None
    home_lon = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.latitude and profile.longitude:
                home_lat = float(profile.latitude)
                home_lon = float(profile.longitude)
        except Exception:
            home_lat = None
            home_lon = None

    for order in popular_orders:
        order.home_distance_km = None
        if (
            home_lat is not None
            and home_lon is not None
            and order.latitude is not None
            and order.longitude is not None
        ):
            try:
                order.home_distance_km = PostcodeGeocoder.calculate_distance(
                    home_lat,
                    home_lon,
                    float(order.latitude),
                    float(order.longitude),
                )
            except Exception:
                order.home_distance_km = None

    if home_lat is not None and home_lon is not None:
        popular_orders.sort(
            key=lambda item: (
                item.home_distance_km is None,
                item.home_distance_km if item.home_distance_km is not None else 10**9,
                -item.favourite_count,
            )
        )

    return popular_orders[:limit]


def _get_descendant_category_ids(category):
    ids = [category.id]
    for child in Category.objects.filter(parent_category=category):
        ids.extend(_get_descendant_category_ids(child))
    return ids


def _get_popular_orders(request, limit=8, category=None):
    orders = Order.objects.filter(status=Order.ACTIVE, direction=Order.TO_LET)
    if category is not None:
        orders = orders.filter(product__category_id__in=_get_descendant_category_ids(category))

    popular_orders = list(
        orders.select_related('product', 'product__category_id', 'user')
        .prefetch_related('images')
        .annotate(favourite_count=Count('favourited_by', distinct=True))
        .order_by('-favourite_count', '-amended')[:limit * 4]
    )

    if not popular_orders:
        return []

    home_lat = None
    home_lon = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.latitude and profile.longitude:
                home_lat = float(profile.latitude)
                home_lon = float(profile.longitude)
        except Exception:
            home_lat = None
            home_lon = None

    for order in popular_orders:
        order.home_distance_km = None
        if (
            home_lat is not None
            and home_lon is not None
            and order.latitude is not None
            and order.longitude is not None
        ):
            try:
                order.home_distance_km = PostcodeGeocoder.calculate_distance(
                    home_lat,
                    home_lon,
                    float(order.latitude),
                    float(order.longitude),
                )
            except Exception:
                order.home_distance_km = None

    if home_lat is not None and home_lon is not None:
        popular_orders.sort(
            key=lambda item: (
                item.home_distance_km is None,
                item.home_distance_km if item.home_distance_km is not None else 10**9,
                -item.favourite_count,
            )
        )

    return popular_orders[:limit]


def _build_biscuit(cat):
    biscuit = [cat]
    biscuit_cat = cat
    while biscuit_cat.parent_category is not None:
        biscuit.append(biscuit_cat.parent_category)
        biscuit_cat = biscuit_cat.parent_category
    return [item for item in biscuit[::-1] if item.slug != 'top']

# @cache_page(60 * 30)
def browseCategory(request, cat_slug=None):
    # try:
    #     cat = Category.objects.get(pk=category_id)
    # except Catspoegory.DoesNotExist:
    #     raise Http404("Category does not exist")
    cat = None
    if cat_slug:
        cat = get_object_or_404(Category, slug=cat_slug)


    categories = common.helpers.get_ordered_child_categories(cat)
    
    chosen_attributes = {}
    all_attributes = {}
    attribute_definitions = cat.get_attribute_definitions()
    active_orders = Order.objects.filter(
        product__category_id=cat,
        status=Order.ACTIVE,
        direction=Order.TO_LET,
    ).select_related('product', 'product__category_id')
    attribute_filters = collect_attribute_filter_options(cat, active_orders, source='order')
    filterable_attributes_count = len(filterable_attribute_definitions(cat))
    sortable_attributes_count = len(sortable_attribute_definitions(cat))
    sort_options = [
        {'value': 'active', 'label': 'Most active'},
        {'value': 'az', 'label': 'A-Z'},
        {'value': 'za', 'label': 'Z-A'},
    ] + attribute_sort_options(cat)

    sort_by = request.GET.get('sort_by', '').strip() or default_sort_value(cat, fallback='active')
    valid_sorts = {'active', 'az', 'za'} | {option['value'] for option in sort_options}
    if sort_by not in valid_sorts:
        sort_by = default_sort_value(cat, fallback='active')
    location = request.GET.get('location', '').strip()
    distance_filter_raw = request.GET.get('distance_filter', 'any')
    if distance_filter_raw in ('any', '-'):
        distance_filter = 'any'
    else:
        try:
            distance_filter = int(distance_filter_raw)
        except (ValueError, TypeError):
            distance_filter = 10

    # Geocode location or fall back to user profile
    browse_lat = None
    browse_lon = None
    browse_postcode = None
    if location:
        coords = PostcodeGeocoder.geocode_location(location)
        if coords:
            browse_lat = float(coords['latitude'])
            browse_lon = float(coords['longitude'])
            browse_postcode = coords.get('postcode', location).upper()
        else:
            messages.warning(request, f'"{location}" could not be found. Please try a UK postcode or town name.')
            location = ''
    elif request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.latitude and profile.longitude:
                browse_lat = float(profile.latitude)
                browse_lon = float(profile.longitude)
                location = profile.postcode or ''
                browse_postcode = (profile.postcode or '').upper()
        except Exception:
            pass

    # Initial queryset ordering for browse cards.
    products = cat.product_set.all().annotate(
        active_lend_orders=Count(
            'order',
            filter=Q(order__status=Order.ACTIVE, order__direction='L'),
            distinct=True,
        )
    )

    available_tags = CategoryTag.objects.filter(
        Q(categories=cat) |
        Q(categories__parent_category=cat) |
        Q(products__category_id=cat) |
        Q(products__category_id__parent_category=cat)
    ).distinct().order_by('name')
    if not available_tags.exists():
        available_tags = CategoryTag.objects.all().order_by('name')

    selected_tag = request.GET.get('tag', '').strip()
    if selected_tag:
        categories = categories.filter(
            Q(tags__slug=selected_tag) | Q(product__tags__slug=selected_tag)
        ).distinct()
        products = products.filter(
            Q(category_id__tags__slug=selected_tag) | Q(tags__slug=selected_tag)
        ).distinct()
        chosen_attributes['tag'] = selected_tag

    filter_source_orders = Order.objects.filter(
        product__in=products,
        status=Order.ACTIVE,
        direction=Order.TO_LET,
    ).select_related('product', 'product__category_id')
    attribute_filters = collect_attribute_filter_options(cat, filter_source_orders, source='order')
    products, chosen_product_attribute_filters = apply_attribute_filters(products, cat, request.GET, source='product')
    chosen_attributes.update(chosen_product_attribute_filters)
    filtered_orders, chosen_order_attribute_filters = apply_attribute_filters(
        Order.objects.filter(
            product__in=products,
            status=Order.ACTIVE,
            direction=Order.TO_LET,
        ).select_related('product', 'product__category_id'),
        cat,
        request.GET,
        source='order',
    )
    chosen_attributes.update(chosen_order_attribute_filters)
    selected_listing_filters = {}
    for definition in attribute_definitions:
        if definition.get('value_source') != 'listing':
            continue
        selected = (request.GET.get(definition['query_param']) or '').strip()
        if selected:
            selected_listing_filters[definition['query_param']] = selected
    if selected_listing_filters:
        matching_product_ids = filtered_orders.values_list('product_id', flat=True).distinct()
        products = products.filter(id__in=matching_product_ids)

    if sort_by == 'az':
        products = products.order_by('name')
    elif sort_by == 'za':
        products = products.order_by('-name')
    else:
        matched_attribute_sort = False
        for definition in sortable_attribute_definitions(cat):
            if sort_by == definition['sort_key_asc']:
                sort_field = field_name_for_definition(definition, source='product')
                if not sort_field or sort_field.startswith('product__'):
                    continue
                products = products.order_by(sort_field, 'name')
                matched_attribute_sort = True
                break
            if sort_by == definition['sort_key_desc']:
                sort_field = field_name_for_definition(definition, source='product')
                if not sort_field or sort_field.startswith('product__'):
                    continue
                products = products.order_by(f"-{sort_field}", 'name')
                matched_attribute_sort = True
                break
        if not matched_attribute_sort:
            products = products.order_by('-active_lend_orders', 'name')

    # make ajax call skip unnecessary info
    if not request.is_ajax():
        biscuit = _build_biscuit(cat)

    active_only = request.GET.get('active_only', None)
    if active_only in ('True', '1', 'on'):
        products = products.filter(best_prices__numberActiveOrders__gt=0)
        chosen_attributes['active_only'] = "True"

    friends_only = request.GET.get('friends_only', None)
    if friends_only and request.user.is_authenticated:
        from friends.models import FriendsHelper
        visible_ids = FriendsHelper.get_visible_friend_ids(request.user)
        products = products.filter(order__user_id__in=visible_ids).distinct()
        chosen_attributes['friends_only'] = "True"

    # Distance filtering + nearest sort (Python-side, requires geocoded location)
    if distance_filter == 0:
        # 0 km filter: show only products with orders in the same postcode
        if browse_postcode:
            products_list = []
            for product in products:
                has_matching_postcode = product.order_set.filter(
                    status=Order.ACTIVE,
                    postcode__iexact=browse_postcode
                ).exists()
                if has_matching_postcode:
                    product._browse_distance = 0
                    products_list.append(product)
            totalProductsCount = len(products_list)
            paginagor = Paginator(products_list, 20)
        else:
            totalProductsCount = 0
            paginagor = Paginator([], 20)
    elif browse_lat and browse_lon:
        products_list = []
        for product in products:
            nearest = None
            for order in product.order_set.filter(status=Order.ACTIVE, latitude__isnull=False):
                d = PostcodeGeocoder.calculate_distance(browse_lat, browse_lon, float(order.latitude), float(order.longitude))
                if nearest is None or d < nearest:
                    nearest = d
            product._browse_distance = nearest
            # include if within distance_filter, or has no geocoded orders (distance unknown), or 'any'
            if distance_filter == 'any' or nearest is None or nearest <= distance_filter:
                products_list.append(product)
        totalProductsCount = len(products_list)
        paginagor = Paginator(products_list, 20)
    else:
        totalProductsCount = products.count()
        paginagor = Paginator(products, 20)

    page = request.GET.get('page')
    try:
        products = paginagor.page(page)
    except PageNotAnInteger:
        products = paginagor.page(1)
    except EmptyPage:
        if request.is_ajax():
            return HttpResponse('')
        products = paginagor.page(paginagor.num_pages)

    # make ajax call skip unnecessary info
    if not request.is_ajax():
        best_bids = []
        best_offers = []
        for product in products:
            productBest = product.best_prices.first()
            best_bid = productBest.bestPricedBid
            if best_bid is not None:
                best_bids.append(best_bid.price)
            else:
                best_bids.append('-')
            best_offer = productBest.bestPricedOffer
            if best_offer is not None:
                best_offers.append(best_offer.price)
            else:
                best_offers.append('-')

        virtual_bids = []
        virtual_offers = []
        if cat.virtual_depth:
            best_prices = cat.best_prices.first()
            temp = [best_prices.bestPricedBid,best_prices.bestPricedBid2,best_prices.bestPricedBid3,best_prices.bestPricedBid4,best_prices.bestPricedBid5]
            for t in temp:
                if t is not None:
                    virtual_bids.append(t)
            temp = [best_prices.bestPricedOffer,best_prices.bestPricedOffer2,best_prices.bestPricedOffer3,best_prices.bestPricedOffer4,best_prices.bestPricedOffer5]
            for t in temp:
                if t is not None:
                    virtual_offers.append(t)

    context = {
        'category' : cat,
        'categories' : categories,
        'products' : products,
        'chosen_attributes' : chosen_attributes,
        'urlencode_string' : urllib.parse.urlencode(chosen_attributes)
    }
    if request.is_ajax():
        return render(request, 'navigation/browse_ajax.html', context)
    else:
        # add additional, non-ajax, parameters
        context['all_attributes'] = all_attributes
        context['attribute_definitions'] = attribute_definitions
        context['attribute_filters'] = attribute_filters
        # context['filterable_attributes'] = filterable_attributes
        context['filterable_attributes_count'] = filterable_attributes_count
        # context['sortable_attributes'] = sortable_attributes
        context['sortable_attributes_count'] = sortable_attributes_count
        context['sort_by'] = sort_by
        context['sort_options'] = sort_options
        context['location'] = location
        context['distance_filter'] = distance_filter
        context['browse_lat'] = browse_lat
        context['browse_lon'] = browse_lon
        context['virtual_offers'] = virtual_offers
        context['virtual_bids'] = virtual_bids
        context['biscuit'] = biscuit
        context['available_tags'] = available_tags
        context['selected_tag'] = selected_tag
        context['totalProductsCount'] = totalProductsCount
        context['best_bids'] = best_bids
        context['best_offers'] = best_offers
        context['browse_popular_orders'] = _get_popular_orders(request, limit=8, category=cat)
        return render(request, 'navigation/browse.html', context)

def productPage(request, product_slug):
    
    product = None
    spot_price_value = 0
    if product_slug:
        product = get_object_or_404(Product, slug=product_slug)
    try:
        cat = product.category_id
    except Category.DoesNotExist:
        raise Http404("Category does not exist")
    sell_orders = product.order_set.filter(status='A', direction='L').prefetch_related('blocked_dates').order_by('price')
    postcode_display_cache = {}

    sort_by = request.GET.get('sort_by', 'nearest')
    VALID_SORTS = {'nearest', 'cheapest', 'newest', 'deposit'}
    if sort_by not in VALID_SORTS:
        sort_by = 'nearest'

    view_mode = request.GET.get('view_mode', 'list')
    if view_mode not in {'list', 'map'}:
        view_mode = 'list'

    needed_date_raw = request.GET.get('needed_date', '').strip()
    needed_date = None
    needed_date_input = ''
    needed_date_display = ''
    if needed_date_raw:
        parsed = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                parsed = datetime.strptime(needed_date_raw, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            messages.warning(request, 'Please choose a valid needed date in DD/MM/YYYY format.')
        else:
            needed_date = parsed
            needed_date_input = needed_date.strftime('%d/%m/%Y')
            needed_date_display = needed_date_input

    needed_days_raw = request.GET.get('needed_days', '').strip()
    needed_days = None
    if needed_days_raw:
        try:
            needed_days = max(1, int(needed_days_raw))
        except (ValueError, TypeError):
            needed_days = None
            needed_days_raw = ''

    # --- location / distance / friends filters ---
    location = request.GET.get('location', '').strip()
    distance_filter_raw = request.GET.get('distance_filter', 'any')
    if distance_filter_raw == 'any':
        distance_filter = 'any'
    else:
        try:
            distance_filter = int(distance_filter_raw)
        except (ValueError, TypeError):
            distance_filter = 'any'

    page_lat = None
    page_lon = None
    search_postcode = None
    
    if location:
        coords = PostcodeGeocoder.geocode_location(location)
        if coords:
            page_lat = float(coords['latitude'])
            page_lon = float(coords['longitude'])
            search_postcode = coords.get('postcode', location).upper()
        else:
            messages.warning(request, f'"{location}" could not be found.')
            location = ''
    elif request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.latitude and profile.longitude:
                page_lat = float(profile.latitude)
                page_lon = float(profile.longitude)
                location = profile.postcode or ''
                search_postcode = (profile.postcode or '').upper()
        except Exception:
            pass

    friends_only = request.GET.get('friends_only', None)
    friend_user_ids = []
    blocked_user_ids = set()
    blocked_by_user_ids = set()
    
    if request.user.is_authenticated:
        from friends.models import FriendsHelper, BlockedUser
        friend_user_ids = list(FriendsHelper.get_visible_friend_ids(request.user))
        blocked_user_ids = FriendsHelper.get_blocked_user_ids(request.user)
        blocked_by_user_ids = FriendsHelper.get_blocked_by_user_ids(request.user)
        if friends_only:
            sell_orders = sell_orders.filter(user_id__in=friend_user_ids)

    # Distance filter (Python-side)
    if distance_filter == 0:
        # 0 km filter: show only listings from the same postcode
        if search_postcode:
            def _same_postcode(qs):
                result = []
                for o in qs:
                    o.distance_km = 0 if o.postcode and o.postcode.upper() == search_postcode else None
                    if o.postcode and o.postcode.upper() == search_postcode:
                        result.append(o)
                return result
            sell_orders = _same_postcode(sell_orders)
        else:
            sell_orders = []
    elif page_lat and page_lon and distance_filter != 'any':
        def _within(qs):
            result = []
            for o in qs:
                if o.latitude and o.longitude:
                    d = PostcodeGeocoder.calculate_distance(page_lat, page_lon, float(o.latitude), float(o.longitude))
                    o.distance_km = d
                    if d <= distance_filter:
                        result.append(o)
                else:
                    o.distance_km = None
                    result.append(o)
            return result
        sell_orders = _within(sell_orders)
    else:
        sell_orders = list(sell_orders)
        for o in sell_orders:
            o.distance_km = None

    # Annotate each order with display information and apply audience visibility rules.
    visible_orders = []
    for o in sell_orders:
        is_owner = request.user.is_authenticated and request.user == o.user
        is_friend_of_lender = request.user.is_authenticated and (o.user_id in friend_user_ids)
        
        # Skip if either user has blocked the other
        if request.user.is_authenticated and not is_owner:
            if o.user_id in blocked_user_ids or o.user_id in blocked_by_user_ids:
                continue

        # Friends-only listings are hidden from non-friends (except owner).
        if o.let_visibility == Order.FRIENDS_ONLY and not is_owner and not is_friend_of_lender:
            continue

        o.main_image = o.images.filter(is_main=True).first()
        o.display_location = ''
        if o.postcode:
            normalized_postcode = o.postcode.strip().upper()
            if normalized_postcode not in postcode_display_cache:
                coords = PostcodeGeocoder.get_coordinates(normalized_postcode)
                postcode_display_cache[normalized_postcode] = (coords or {}).get('display_name', normalized_postcode)
            o.display_location = postcode_display_cache[normalized_postcode]
        o.available_on_needed_date = None
        if needed_date:
            if needed_date > o.expiry_date.date():
                o.available_on_needed_date = False
            else:
                o.available_on_needed_date = not o.blocked_dates.filter(date=needed_date).exists()

        can_use_mates_rate = (
            is_friend_of_lender
            and o.let_visibility in (Order.FRIENDS_ONLY, Order.FRIENDS_AND_PUBLIC)
            and o.mates_rates is not None
        )
        o.is_mates_rate_applied = can_use_mates_rate
        o.display_price = o.mates_rates if can_use_mates_rate else o.price
        if can_use_mates_rate and o.mates_deposit is not None:
            o.display_deposit = o.mates_deposit
        else:
            o.display_deposit = o.deposit
        o.total_price = (o.display_price * needed_days) if needed_days else None

        visible_orders.append(o)

    sell_orders = visible_orders

    favourite_order_ids = set()
    if request.user.is_authenticated:
        favourite_order_ids = set(
            FavouriteOrder.objects.filter(
                user=request.user,
                order_id__in=[order.id for order in sell_orders],
            ).values_list('order_id', flat=True)
        )
    for order in sell_orders:
        order.is_favourite = order.id in favourite_order_ids

    user_feedback_breakdowns = get_user_feedback_breakdown_map([o.user_id for o in sell_orders])
    for order in sell_orders:
        order.user_feedback_stats = user_feedback_breakdowns.get(order.user_id, {})

    # Sort
    if sort_by == 'nearest':
        sell_orders.sort(key=lambda o: o.distance_km if o.distance_km is not None else 99999)
    elif sort_by == 'cheapest':
        sell_orders.sort(key=lambda o: o.total_price if o.total_price is not None else float(o.price))
    elif sort_by == 'newest':
        sell_orders.sort(key=lambda o: o.create_date, reverse=True)
    elif sort_by == 'deposit':
        sell_orders.sort(key=lambda o: float(o.deposit) if o.deposit is not None else 0)
    
    biscuit = _build_biscuit(cat)

    all_time_stats = {
        'high_price' : None,
        'high_price_datetime' : None,
        'high_price_pct' : None,
        'high_price_pct_datetime' : None,
        'low_price' : None,
        'low_price_datetime' : None,
        'low_price_pct' : None,
        'low_price_pct_datetime' : None,
        'avg_price' : None,
        'avg_price_pct' : None,
    }
    high_price = product.transaction_set.order_by('-price').first()
    if high_price is not None:
        all_time_stats['high_price'] = high_price.price
        all_time_stats['high_price_datetime'] = high_price.created
    high_price_pct = product.transaction_set.order_by('-price_as_pct_spot_value').first()
    if high_price_pct is not None:
        all_time_stats['high_price_pct'] = high_price_pct.price_as_pct_spot_value
        all_time_stats['high_price_pct_datetime'] = high_price_pct.created
        
    low_price = product.transaction_set.order_by('price').first()
    if low_price is not None:
        all_time_stats['low_price'] = low_price.price
        all_time_stats['low_price_datetime'] = low_price.created
    low_price_pct = product.transaction_set.order_by('price_as_pct_spot_value').first()
    if low_price_pct is not None:
        all_time_stats['low_price_pct'] = low_price_pct.price_as_pct_spot_value
        all_time_stats['low_price_pct_datetime'] = low_price_pct.created

    if len(product.transaction_set.all()) > 0:
        # moving from django default to custom
        # avg_price = product.transaction_set.aggregate(Avg('price'))['price__avg']
        # TODO: FIX away from -1
        avg_price = (
            Transaction.objects
            .filter(product_id=product.id)
            .aggregate(average_price=Avg('price'))
        )["average_price"]
        # avg_price = list(Transaction.objects.mongo_aggregate([
        #     {
        #         '$match':
        #         {
        #             'product_id': product.id,
        #         }
        #     },
        # { '$group' :
        #     {
        #         '_id': 'null',
        #         'average_price': {
        #         '$avg': '$price'
        #         }
        #     }
        # }
        # ]))[0]['average_price']
        
        if avg_price is not None:
            all_time_stats['avg_price'] = avg_price

        # TODO Fix this
        # avg_price_pct = -1
        avg_price_pct = (
            Transaction.objects
            .filter(product_id=product.id)
            .aggregate(average_price=Avg("price_as_pct_spot_value"))
        )["average_price"]
        # avg_price_pct = product.transaction_set.aggregate(Avg('price_as_pct_spot_value'))['price_as_pct_spot_value__avg']
        # avg_price_pct = list(Transaction.objects.mongo_aggregate([
        #     {
        #         '$match':
        #         {
        #             'product_id': product.id,
        #         }
        #     },
        # { '$group' :
        #     {
        #         '_id': 'null',
        #         'price_as_pct_spot_value': {
        #         '$avg': '$price_as_pct_spot_value'
        #         }
        #     }
        # }
        # ]))[0]['price_as_pct_spot_value']

        if avg_price_pct is not None:
            all_time_stats['avg_price_pct'] = avg_price_pct
    else:
        avg_price = None

    last_transactions = []
    last_transactions = product.transaction_set.order_by('-created', '-pk')[:5]

    order_quotes = []
    any_year_order_quotes = []

    template = loader.get_template('navigation/productPage.html')
    context = {
        'category' : cat,
        'product'  : product,
        'sell_orders'  : sell_orders,
        'biscuit' : biscuit, 
        'spot_price_value' : spot_price_value,
        'all_time_stats' : all_time_stats,
        'last_transactions' : last_transactions,
        'order_quotes' : order_quotes,
        'any_year_order_quotes' : any_year_order_quotes,
        'location': location,
        'distance_filter': distance_filter,
        'page_lat': page_lat,
        'page_lon': page_lon,
        'friends_only': friends_only,
        'friend_user_ids': friend_user_ids,
        'needed_date': needed_date,
        'needed_date_input': needed_date_input,
        'needed_date_display': needed_date_display,
        'needed_days': needed_days_raw if needed_days_raw else '',
        'needed_days_int': needed_days,
        'sort_by': sort_by,
        'view_mode': view_mode,
    }
    return HttpResponse(template.render(context, request))

def seeAll(request):
    allCategories = Category.objects.all()
    template = loader.get_template('navigation/seeAll.html')
    # output = ', '.join([q.title for q in allCategories])
    context = {
        'allCategories' : allCategories
    }
    return HttpResponse(template.render(context, request))


def index(request):

    # run static migration via celery task to (hopefully) avoid webserver timeouts
    runStaticMigration.delay() 
    # listEmptyCategories.delay()

    try:
        latest_order = Order.objects.latest('amended')
        latestOrderAmend = slugify(str(latest_order.amended))
    except Order.DoesNotExist:
        latestOrderAmend = "NO_ORDERS"

    primary_cache_key = "common_index_last_order_amend_" + latestOrderAmend
    context = cache.get('navigation_index_context'+latestOrderAmend)
    if not context:

        # only store a cached page if summary updates arent running
        # decide before we pull out the data if we're going to cache or not - else there's a race
        updateRunning, created = System.objects.get_or_create(name="summary_price_update_running")
        if created:
            updateRunning.value = "False"
            updateRunning.save()

        # # not recursive for now - we'll mandate all products under the defined categories
        # metals = ['gold','silver','platinum','palladium']
        # type_ = ['coins','bullion']
        # coin_weights = ['1/4 Oz', '1/2 Oz', '1/10 Oz', '1 Oz']
        # bullion_weights = ['1kg','500g','100g','50g','1 Oz','20g','10g','2.5g','1g']

        # slugs = []
        # for m in metals:
        #     # for t in type_:
        #     for w in coin_weights:
        #         slugs.append(slugify(w+'-'+m+'-coins'))
        #     for w in bullion_weights:
        #         slugs.append(slugify(w+'-'+m+'-bars'))

        # results = {}

        # for slug_ in slugs:
        #     root_category = Category.objects.get(slug=slug_)
        #     categoryBest = root_category.best_prices.first().bestPricedOffer
        #     results[slug_] = categoryBest

        
        # gold = Category.objects.get(slug='gold')
        # silver = Category.objects.get(slug='silver')
        # platinum = Category.objects.get(slug='platinum')
        # palladium = Category.objects.get(slug='palladium')

        context = { 
            # 'gold' : gold,
            # 'silver' : silver,
            # 'platinum' : platinum,
            # 'palladium' : palladium,
            'cache_timeout' : 600,
            # 'primary_cache_key_gold' : primary_cache_key, # TODO - if site gets enough orders
            # 'primary_cache_key_silver' : primary_cache_key,
            # 'primary_cache_key_platinum' : primary_cache_key,
            # 'primary_cache_key_palladium' : primary_cache_key,
        }
        
        # for key, val in results.items():
        #     if val is not None:
        #         key = key.replace("-", "").replace(".","_")
        #         context[key] = val
        #         keyP = key + 'P'
        #         context[keyP] = val.product

        if updateRunning.value == "False":    
            cache.set('navigation_index_context'+latestOrderAmend, context, None) # no expiry

    context = dict(context or {})
    context['browse_categories'] = _get_homepage_categories(limit=12)
    context['popular_orders'] = _get_homepage_popular_orders(request, limit=8)

    template = loader.get_template('navigation/index.html')

    return HttpResponse(template.render(context, request))


@ajax_required
def expandOrder(request):
    order_id = request.GET.get('order_id', None)
    order = get_object_or_404(Order, id=order_id)
    orderImages = order.images.filter(active=True)
    price_bands = order.price_bands.all()
    friendship = None
    friendship_status = None
    friendship_i_sent = False
    is_friend_of_lender = False
    display_price = order.price
    display_deposit = order.deposit
    is_owner = request.user.is_authenticated and request.user == order.user
    
    if request.user.is_authenticated and request.user != order.user:
        from friends.models import Friendship, FriendsHelper, BlockedUser
        
        # Check if blocked
        if BlockedUser.objects.filter(
            Q(blocked_by=request.user, blocked_user=order.user) |
            Q(blocked_by=order.user, blocked_user=request.user)
        ).exists():
            return HttpResponseForbidden('You cannot view this listing.')
        
        is_friend_of_lender = order.user_id in FriendsHelper.get_visible_friend_ids(request.user)
        if is_friend_of_lender and order.mates_rates is not None and order.let_visibility in (Order.FRIENDS_ONLY, Order.FRIENDS_AND_PUBLIC):
            display_price = order.mates_rates
            if order.mates_deposit is not None:
                display_deposit = order.mates_deposit
        friendship = Friendship.objects.filter(
            Q(user_from=request.user, user_to=order.user) |
            Q(user_from=order.user, user_to=request.user)
        ).first()
        if friendship:
            friendship_status = friendship.status
            friendship_i_sent = friendship.user_from_id == request.user.id

    if order.let_visibility == Order.FRIENDS_ONLY and not is_owner and not is_friend_of_lender:
        return HttpResponseForbidden('This listing is only visible to friends.')
    template = loader.get_template('navigation/orderAjax.html')
    content = {
        'order': order,
        'orderImages': orderImages,
        'price_bands': price_bands,
        'friendship': friendship,
        'friendship_status': friendship_status,
        'friendship_i_sent': friendship_i_sent,
        'is_friend_of_lender': is_friend_of_lender,
        'display_price': display_price,
        'display_deposit': display_deposit,
        'order_user_feedback_stats': get_user_feedback_breakdown(user_id=order.user_id),
    }
    return HttpResponse(template.render(content, request))
