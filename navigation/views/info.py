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


@login_required
def suggestCategory(request):
    current_category = None
    category_id = request.GET.get('category_id') or request.POST.get('category_id')
    if category_id:
        try:
            current_category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            current_category = None

    if request.method == 'POST':
        form = CategorySuggestionForm(request.POST, request.FILES)
        if form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.user = request.user
            suggestion.category = current_category
            suggestion.save()
            messages.success(request, 'Thanks. Your category suggestion has been submitted for admin review.')

            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('navigation:seeAll')
    else:
        form = CategorySuggestionForm()

    context = {
        'form': form,
        'current_category': current_category,
        'next': request.GET.get('next', ''),
    }
    return render(request, 'navigation/suggest_category.html', context)


