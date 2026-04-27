from django.urls import path
from django.urls import re_path
from . import views

app_name='navigation'
urlpatterns = [
    path('browse/<slug:cat_slug>/', views.browseCategory, name='browseCategory'),
    path('product_page/<slug:product_slug>/', views.productPage, name='productPage'),
    path('expand_order/', views.expandOrder, name='expandOrder'),
    path('search/', views.search, name='search'),
    path('how_it_works/', views.howItWorks, name='howItWorks'),
    path('fees_and_charges/', views.feesAndCharges, name='feesAndCharges'),
    path('help_and_support/', views.helpAndSupport, name='helpAndSupport'),
    path('guide_for_buyers/', views.buyersGuide, name='buyersGuide'),
    path('guide_for_sellers/', views.sellersGuide, name='sellersGuide'),
    path('transaction_guide/', views.transactionGuide, name='transactionGuide'),
    path('physical_ownership_guide/', views.physicalOwnershipGuide, name='physicalOwnershipGuide'),
    path('site_feedback/', views.siteFeedback, name='siteFeedback'),
    path('suggest_category/', views.suggestCategory, name='suggestCategory'),
    path('about_us/', views.aboutUs, name='aboutUs'),
    path('terms_and_conditions/', views.termsAndConditions, name='termsAndConditions'),
    path('search_by_postcode/', views.search_by_postcode, name='search_by_postcode'),
    re_path(r'$', views.seeAll, name='seeAll'),
]