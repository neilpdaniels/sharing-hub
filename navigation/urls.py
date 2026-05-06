from django.urls import path
from django.urls import re_path
from . import views

app_name = 'navigation'
urlpatterns = [
    path('browse/<slug:cat_slug>/', views.browseCategory, name='browseCategory'),
    path('product_page/<slug:product_slug>/', views.productPage, name='productPage'),
    path('expand_order/', views.expandOrder, name='expandOrder'),
    path('search/', views.search, name='search'),
    path('suggest_category/', views.suggestCategory, name='suggestCategory'),
    path('search_by_postcode/', views.search_by_postcode, name='search_by_postcode'),
    path('whats_popular/', views.whats_popular, name='whats_popular'),
    path('whats_popular_admin/', views.whats_popular_admin, name='whats_popular_admin'),
    re_path(r'$', views.seeAll, name='seeAll'),
]
