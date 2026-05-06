from django.shortcuts import render


def how_it_works(request):
    return render(request, 'pages/how_it_works.html')


def fees_and_charges(request):
    return render(request, 'pages/fees_and_charges.html')


def help_and_support(request):
    return render(request, 'pages/help_and_support.html')


def buyers_guide(request):
    return render(request, 'pages/information_for_buyers.html')


def sellers_guide(request):
    return render(request, 'pages/information_for_sellers.html')


def transaction_guide(request):
    return render(request, 'pages/transaction_workflow.html')


def physical_ownership_guide(request):
    return render(request, 'pages/physical_ownership.html')


def site_feedback(request):
    return render(request, 'pages/site_feedback.html')


def about_us(request):
    return render(request, 'pages/about_us.html')


def terms_and_conditions(request):
    return render(request, 'pages/terms_and_conditions.html')
