from django.urls import path

from . import views

app_name = 'pages'

urlpatterns = [
    path('how_it_works/', views.how_it_works, name='howItWorks'),
    path('fees_and_charges/', views.fees_and_charges, name='feesAndCharges'),
    path('help_and_support/', views.help_and_support, name='helpAndSupport'),
    path('guide_for_buyers/', views.buyers_guide, name='buyersGuide'),
    path('guide_for_sellers/', views.sellers_guide, name='sellersGuide'),
    path('transaction_guide/', views.transaction_guide, name='transactionGuide'),
    path('physical_ownership_guide/', views.physical_ownership_guide, name='physicalOwnershipGuide'),
    path('site_feedback/', views.site_feedback, name='siteFeedback'),
    path('about_us/', views.about_us, name='aboutUs'),
    path('terms_and_conditions/', views.terms_and_conditions, name='termsAndConditions'),
]
