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
from common.models import (
    BestPricedForCategory, BestPricedForProduct, Category, CategoryTag,
    Order, Product, System,
)
from common.tasks import listEmptyCategories, runStaticMigration
from transaction.models import Transaction

from ..forms import CategorySuggestionForm
from ..models import SearchHistory


logger = logging.getLogger(__name__)


def search(request):
    """
    Combined text + category + location/distance search.
    Accepts: q (text), category (slug of child of 'top'), location (postcode or town), distance (km), sort_by.
    """

    q = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    category_slug = request.GET.get('category', '')
    distance_raw = request.GET.get('distance', '25')
    if distance_raw == 'any':
        max_distance_km = 'any'
    else:
        try:
            max_distance_km = int(distance_raw)
        except (ValueError, TypeError):
            max_distance_km = 25
    sort_by = request.GET.get('sort_by', 'newest')

    latitude = None
    longitude = None
    search_postcode = None
    display_location = None
    location_not_found = False

    # Top-level categories for the filter dropdown
    try:
        top_cat = Category.objects.get(slug='top')
        top_categories = Category.objects.filter(parent_category=top_cat).order_by('title')
    except Category.DoesNotExist:
        top_categories = Category.objects.none()

    # Fall back to profile postcode for logged-in users
    if not location and request.user.is_authenticated:
        try:
            user_profile = request.user.profile
            location = user_profile.postcode or ''
            search_postcode = (user_profile.postcode or '').upper()
            if user_profile.latitude and user_profile.longitude:
                latitude = user_profile.latitude
                longitude = user_profile.longitude
                display_location = location
        except Exception:
            pass

    # Geocode the location string if we don't have coords yet
    if location and latitude is None:
        coords = PostcodeGeocoder.geocode_location(location)
        if coords:
            latitude = coords['latitude']
            longitude = coords['longitude']
            search_postcode = coords.get('postcode', location).upper()
            display_location = coords.get('display_name', location)
            if request.user.is_authenticated:
                try:
                    user_profile = request.user.profile
                    user_profile.latitude = latitude
                    user_profile.longitude = longitude
                    user_profile.save()
                except Exception:
                    pass
        elif location:
            location_not_found = True
            messages.error(request, f'"{location}" could not be found. Please try a postcode or UK town name.')

    # Start with all active orders
    # Log the search if a term or location was supplied, deduplicating by IP+term+day
    if q or (location and not location_not_found):
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '')
        ) or None
        today = timezone.now().date()
        already_logged = (
            ip and q and
            SearchHistory.objects.filter(
                ip_address=ip,
                search_term__iexact=q,
                searched_at__date=today,
            ).exists()
        )
        if not already_logged:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                search_term=q,
                location=display_location or location,
                ip_address=ip,
            )

    orders = Order.objects.select_related('product', 'user', 'product__category_id').filter(status=Order.ACTIVE)

    def get_descendant_ids(cat):
        ids = [cat.id]
        for child in Category.objects.filter(parent_category=cat):
            ids.extend(get_descendant_ids(child))
        return ids

    # Filter by category (and its descendants)
    selected_category = None
    category_ids = None
    if category_slug:
        try:
            selected_category = Category.objects.get(slug=category_slug)
            category_ids = get_descendant_ids(selected_category)
            orders = orders.filter(product__category_id__in=category_ids)
        except Category.DoesNotExist:
            pass

    # Text search — filter by product name / description
    if q:
        orders = orders.filter(
            product__name__icontains=q
        ) | Order.objects.filter(
            status=Order.ACTIVE,
            product__description__icontains=q
        )
        if category_slug and selected_category:
            orders = orders.filter(product__category_id__in=category_ids)

    # Distance filtering
    if max_distance_km == 0:
        # 0 km filter: show only orders from the same postcode
        if search_postcode:
            result_orders = []
            for order in orders:
                if order.postcode and order.postcode.upper() == search_postcode:
                    order.distance = 0
                    result_orders.append(order)
            nearby_orders = result_orders
        else:
            nearby_orders = []
    elif latitude and longitude and not location_not_found:
        result_orders = []
        for order in orders:
            if order.latitude and order.longitude:
                dist = PostcodeGeocoder.calculate_distance(latitude, longitude, order.latitude, order.longitude)
                order.distance = dist
                if max_distance_km == 'any' or dist <= max_distance_km:
                    result_orders.append(order)
            elif max_distance_km == 'any':
                order.distance = None
                result_orders.append(order)
        nearby_orders = result_orders
    else:
        nearby_orders = list(orders)
        for o in nearby_orders:
            o.distance = None

    # Sorting
    if sort_by == 'distance' and latitude:
        nearby_orders.sort(key=lambda o: (o.distance is None, o.distance or 0))
    elif sort_by == 'price':
        nearby_orders.sort(key=lambda o: o.price or 0)
    else:  # newest
        nearby_orders.sort(key=lambda o: o.create_date, reverse=True)

    # Paginate
    paginator = Paginator(nearby_orders, 20)
    page = request.GET.get('page', 1)
    try:
        orders_page = paginator.page(page)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)

    related_products = Product.objects.none()
    if q or selected_category:
        related_products = Product.objects.select_related('category_id')

        if category_ids:
            related_products = related_products.filter(category_id__in=category_ids)

        if q:
            related_products = related_products.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(category_id__title__icontains=q)
            )

        related_products = (
            related_products
            .annotate(active_order_count=Count('order', filter=Q(order__status=Order.ACTIVE), distinct=True))
            .filter(active_order_count=0)
            .order_by('name')
            .distinct()[:12]
        )

    context = {
        'q': q,
        'location': location,
        'display_location': display_location,
        'max_distance': max_distance_km,
        'sort_by': sort_by,
        'category_slug': category_slug,
        'top_categories': top_categories,
        'selected_category': selected_category,
        'orders': orders_page,
        'related_products': related_products,
        'total_results': len(nearby_orders),
        'search_performed': bool(q or category_slug or (location and not location_not_found)),
        'location_not_found': location_not_found,
        'location_active': bool(latitude and longitude and not location_not_found),
        'is_logged_in': request.user.is_authenticated,
    }
    template = loader.get_template('navigation/search.html')
    return HttpResponse(template.render(context, request))


def search_by_postcode(request):
    """
    Search for transactions (wanted/to lend) by postcode or town and distance.
    
    Allows both logged-in users (uses their postcode) and guests (enter postcode/town).
    Supports filtering by distance and sorting by distance.
    """
    from transaction.helpers import filter_transactions_by_distance, get_transaction_price_for_user, get_transaction_deposit_for_user
    
    context = {}
    location = None      # raw input string
    display_location = None  # human-friendly resolved name
    latitude = None
    longitude = None
    max_distance_km = 25  # Default search radius
    sort_by = request.GET.get('sort_by', 'newest')  # newest, distance, price
    direction_filter = request.GET.get('direction', 'W')  # W for WANTED, L for TO_LET, Both for all
    
    # Get location from request (always allow override)
    location = request.GET.get('location', '').strip() or request.POST.get('location', '').strip()

    # If logged-in and no location entered, fall back to profile postcode
    if not location and request.user.is_authenticated:
        try:
            user_profile = request.user.profile
            location = user_profile.postcode or ''
            # Use cached coordinates if available
            if user_profile.latitude and user_profile.longitude:
                latitude = user_profile.latitude
                longitude = user_profile.longitude
                display_location = location
        except Exception:
            pass
    
    max_distance_km = int(request.GET.get('distance', 25))
    
    context = {
        'location': location,
        'max_distance': max_distance_km,
        'sort_by': sort_by,
        'direction_filter': direction_filter,
        'is_logged_in': request.user.is_authenticated,
    }
    
    # If we have a location, geocode it and search
    if location and not latitude:
        coords = PostcodeGeocoder.geocode_location(location)
        
        if coords:
            latitude = coords['latitude']
            longitude = coords['longitude']
            display_location = coords.get('display_name', location)

            # Cache in profile for logged-in users
            if request.user.is_authenticated:
                try:
                    user_profile = request.user.profile
                    user_profile.latitude = latitude
                    user_profile.longitude = longitude
                    user_profile.save()
                except Exception:
                    pass

    if latitude and longitude:
        context['display_location'] = display_location

        # Get all active transactions (WANTED/TO LEND)
        transactions = Transaction.objects.select_related(
            'order_passive', 'order_passive__product', 
            'user_aggressive', 'user_passive'
        ).filter(
            transaction_status=Transaction.NEW,
            order_passive__status=Order.ACTIVE
        )
        
        # Filter by direction if specified
        if direction_filter == 'W':
            transactions = transactions.filter(order_passive__direction=Order.WANTED)
        elif direction_filter == 'L':
            transactions = transactions.filter(order_passive__direction=Order.TO_LET)
        
        # Filter by distance
        nearby_transactions = filter_transactions_by_distance(
            transactions,
            latitude, longitude,
            max_distance_km
        )
        
        # Sort
        if sort_by == 'distance':
            nearby_transactions.sort(key=lambda x: x.distance)
        elif sort_by == 'price':
            if request.user.is_authenticated:
                nearby_transactions.sort(key=lambda x: get_transaction_price_for_user(x, request.user))
            else:
                nearby_transactions.sort(key=lambda x: x.price)
        # else: newest (default, already in reverse chronological order)
        
        # Add pricing info to each transaction
        for txn in nearby_transactions:
            if request.user.is_authenticated:
                txn.display_price = get_transaction_price_for_user(txn, request.user)
                txn.display_deposit = get_transaction_deposit_for_user(txn, request.user)
            else:
                txn.display_price = txn.price
                txn.display_deposit = txn.deposit
        
        # Paginate results
        paginator = Paginator(nearby_transactions, 20)
        page = request.GET.get('page', 1)
        try:
            transactions_page = paginator.page(page)
        except PageNotAnInteger:
            transactions_page = paginator.page(1)
        except EmptyPage:
            transactions_page = paginator.page(paginator.num_pages)
        
        context.update({
            'transactions': transactions_page,
            'total_results': len(nearby_transactions),
            'latitude': latitude,
            'longitude': longitude,
            'search_performed': True,
        })
    elif location:
        # Had a location string but couldn't geocode it
        context['search_performed'] = True
        context['location_not_found'] = True
        messages.error(request, f'"{location}" could not be found. Please try a postcode or UK town name.')
    
    template = loader.get_template('navigation/search_by_postcode.html')
    return HttpResponse(template.render(context, request))


@login_required
def whats_popular(request):
    """
    Public popular searches — only shows terms that match a known category or
    product, so users see what's trending for items we actually stock/list.
    """

    FETCH_LIMIT = 500    # top N terms to consider before filtering
    DISPLAY_LIMIT = 50   # max matched results to show
    ORDER_DISTANCES = [5, 10, 20]

    now = timezone.now()
    week_ago  = now - timezone.timedelta(days=7)
    month_ago = now - timezone.timedelta(days=30)
    year_ago  = now - timezone.timedelta(days=365)

    distance_raw = request.GET.get('distance', '')
    try:
        _d = int(distance_raw) if distance_raw.strip() else None
        max_distance_km = None if (_d is None or _d >= 50) else _d
    except (ValueError, TypeError, AttributeError):
        max_distance_km = None

    user_lat = user_lon = user_postcode = None
    try:
        profile = request.user.profile
        if profile.latitude and profile.longitude:
            user_lat = float(profile.latitude)
            user_lon = float(profile.longitude)
        user_postcode = (profile.postcode or '').upper().replace(' ', '')
    except Exception:
        pass
    has_location = bool(user_lat and user_lon)

    sh_base = SearchHistory.objects.filter(searched_at__gte=year_ago, search_term__gt='')

    if has_location and max_distance_km is not None:
        nearby_user_ids = PostcodeGeocoder.get_nearby_user_ids(
            user_lat, user_lon, max_distance_km, user_postcode
        )
        sh_base = sh_base.filter(user__in=nearby_user_ids)

    # Fetch top terms (by popularity over the past year)
    all_top_terms = list(
        sh_base
        .values('search_term')
        .annotate(total=Count('id'))
        .order_by('-total')[:FETCH_LIMIT]
    )

    # Preload all products and categories in memory to avoid N+1 per term
    all_products = list(Product.objects.values('name', 'slug'))
    all_categories = list(
        Category.objects.exclude(slug='top').values('title', 'slug')
    )

    def find_matches(term):
        """Return up to 5 matched products/categories for this search term."""
        term_lower = term.lower()
        matched = []
        seen_slugs = set()
        for p in all_products:
            if term_lower in p['name'].lower() and p['slug'] not in seen_slugs:
                seen_slugs.add(p['slug'])
                matched.append({'type': 'product', 'name': p['name'], 'slug': p['slug']})
                if len(matched) >= 5:
                    break
        for c in all_categories:
            if term_lower in c['title'].lower() and c['slug'] not in seen_slugs:
                seen_slugs.add(c['slug'])
                matched.append({'type': 'category', 'name': c['title'], 'slug': c['slug']})
                if len(matched) >= 5:
                    break
        return matched

    # Collect matched terms up to DISPLAY_LIMIT
    matched_rows = []
    for row in all_top_terms:
        if len(matched_rows) >= DISPLAY_LIMIT:
            break
        matches = find_matches(row['search_term'])
        if matches:
            matched_rows.append((row, matches))

    results = []
    for rank, (row, matches) in enumerate(matched_rows, 1):
        term = row['search_term']

        week_count = sh_base.filter(
            searched_at__gte=week_ago, search_term__iexact=term
        ).count()

        matching_orders = list(
            Order.objects.filter(status=Order.ACTIVE, product__name__icontains=term)
            .only('latitude', 'longitude')
        )
        if has_location:
            counts = {d: 0 for d in ORDER_DISTANCES}
            for o in matching_orders:
                if o.latitude and o.longitude:
                    dist = PostcodeGeocoder.calculate_distance(
                        user_lat, user_lon, float(o.latitude), float(o.longitude)
                    )
                    for d in ORDER_DISTANCES:
                        if dist <= d:
                            counts[d] += 1
            orders_5 = counts[5]
            orders_10 = counts[10]
            orders_20 = counts[20]
        else:
            n = len(matching_orders)
            orders_5 = orders_10 = orders_20 = n

        results.append({
            'rank': rank,
            'term': term,
            'week': week_count,
            'year': row['total'],
            'matches': matches,
            'orders_5': orders_5,
            'orders_10': orders_10,
            'orders_20': orders_20,
        })

    context = {
        'results': results,
        'distance': distance_raw,
        'max_distance_km': max_distance_km,
        'has_location': has_location,
    }
    return render(request, 'navigation/whats_popular.html', context)


@staff_member_required
def whats_popular_admin(request):
    """
    Admin-only: show ALL top searched-for terms including those with no
    matching products (useful for spotting demand gaps).

    The distance slider filters which searches are included (by proximity of
    the user who made the search). Open order counts are always shown at fixed
    buckets of 5 km, 10 km and 20 km from the logged-in user's location.

    Supports infinite scroll: append ?format=json&page=N for JSON responses.
    """

    PAGE_SIZE = 10
    ORDER_DISTANCES = [5, 10, 20]

    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)
    month_ago = now - timezone.timedelta(days=30)
    prev_month_start = now - timezone.timedelta(days=60)
    year_ago = now - timezone.timedelta(days=365)

    # Slider: filters search history by distance of the searcher from this user
    # Values 0–49 km are exact; 50 (slider max) means "any distance"
    distance_raw = request.GET.get('distance', '')
    try:
        _d = int(distance_raw) if distance_raw.strip() else None
        max_distance_km = None if (_d is None or _d >= 50) else _d
    except (ValueError, TypeError, AttributeError):
        max_distance_km = None  # None == any distance

    try:
        page = max(1, int(request.GET.get('page', 1) or 1))
    except (ValueError, TypeError):
        page = 1
    is_ajax = request.GET.get('format') == 'json'

    # User's cached GPS location from profile
    user_lat = user_lon = user_postcode = None
    try:
        profile = request.user.profile
        if profile.latitude and profile.longitude:
            user_lat = float(profile.latitude)
            user_lon = float(profile.longitude)
        user_postcode = (profile.postcode or '').upper().replace(' ', '')
    except Exception:
        pass

    has_location = bool(user_lat and user_lon)

    # Base SearchHistory queryset, scoped to the past year, non-empty terms
    sh_base = SearchHistory.objects.filter(searched_at__gte=year_ago, search_term__gt='')

    # If the user has a location and a distance is set, restrict to searches
    # made by users who are within that radius.
    if has_location and max_distance_km is not None:
        nearby_user_ids = PostcodeGeocoder.get_nearby_user_ids(
            user_lat, user_lon, max_distance_km, user_postcode
        )
        sh_base = sh_base.filter(user__in=nearby_user_ids)

    # Aggregate top terms and paginate
    top_terms_qs = (
        sh_base
        .values('search_term')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    total_terms = top_terms_qs.count()
    offset = (page - 1) * PAGE_SIZE
    page_terms = list(top_terms_qs[offset:offset + PAGE_SIZE])
    has_next = (offset + PAGE_SIZE) < total_terms

    results = []
    for idx, row in enumerate(page_terms):
        term = row['search_term']
        rank = offset + idx + 1

        week_count = sh_base.filter(searched_at__gte=week_ago, search_term__iexact=term).count()
        month_count = sh_base.filter(searched_at__gte=month_ago, search_term__iexact=term).count()
        prev_month_count = sh_base.filter(
            searched_at__gte=prev_month_start,
            searched_at__lt=month_ago,
            search_term__iexact=term,
        ).count()

        # 30-point daily sparkline for the past 30 days
        daily = (
            sh_base
            .filter(searched_at__gte=month_ago, search_term__iexact=term)
            .annotate(day=TruncDate('searched_at'))
            .values('day')
            .annotate(n=Count('id'))
            .order_by('day')
        )
        day_map = {entry['day'].isoformat(): entry['n'] for entry in daily}
        sparkline = [
            day_map.get((now - timezone.timedelta(days=i)).date().isoformat(), 0)
            for i in range(29, -1, -1)
        ]

        # Open orders at fixed distances (5 km, 10 km, 20 km)
        matching_orders = list(
            Order.objects.filter(status=Order.ACTIVE, product__name__icontains=term)
            .only('latitude', 'longitude', 'postcode')
        )

        if has_location:
            counts = {d: 0 for d in ORDER_DISTANCES}
            for o in matching_orders:
                if o.latitude and o.longitude:
                    dist = PostcodeGeocoder.calculate_distance(
                        user_lat, user_lon, float(o.latitude), float(o.longitude)
                    )
                    for d in ORDER_DISTANCES:
                        if dist <= d:
                            counts[d] += 1
            orders_5 = counts[5]
            orders_10 = counts[10]
            orders_20 = counts[20]
        else:
            # No location on profile — show total counts for all distances
            n = len(matching_orders)
            orders_5 = orders_10 = orders_20 = n

        results.append({
            'rank': rank,
            'term': term,
            'week': week_count,
            'month': month_count,
            'prev_month': prev_month_count,
            'year': row['total'],
            'sparkline': sparkline,
            'orders_5': orders_5,
            'orders_10': orders_10,
            'orders_20': orders_20,
        })

    if is_ajax:
        return JsonResponse({'results': results, 'has_next': has_next, 'next_page': page + 1})

    context = {
        'results': results,
        'distance': distance_raw,
        'max_distance_km': max_distance_km,
        'has_location': has_location,
        'has_next': has_next,
        'page': page,
    }
    return render(request, 'navigation/whats_popular_admin.html', context)
