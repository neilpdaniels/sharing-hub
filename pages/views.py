from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import render

from common.failures import record_site_failure
from common.security import verify_turnstile_token


def how_it_works(request):
    return render(request, 'pages/how_it_works.html')


def safety(request):
    return render(request, 'pages/safety.html')


def fees_and_charges(request):
    return render(request, 'pages/fees_and_charges.html')


def help_and_support(request):
    show_turnstile = True
    captcha_error = ''

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        email = (request.POST.get('email') or '').strip()
        subject = (request.POST.get('subject') or '').strip()
        message = (request.POST.get('message') or '').strip()

        token = (request.POST.get('cf-turnstile-response') or '').strip()
        if not verify_turnstile_token(token, request.META.get('REMOTE_ADDR', '')):
            captcha_error = 'Human verification failed. Please try again.'

        if not captcha_error and (not name or not email or not subject or not message):
            messages.error(request, 'Please complete all fields before submitting.')
        elif not captcha_error:
            support_to = 'admin@rentalution.co.uk'
            try:
                send_mail(
                    subject=f'Help & Support: {subject}',
                    message=(
                        f'From: {name}\n'
                        f'Email: {email}\n\n'
                        f'Message:\n{message}'
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[support_to],
                    fail_silently=False,
                )
            except Exception as exc:
                record_site_failure(
                    'Help & Support email failed',
                    details=f'Failed to send support email from {email or "unknown sender"}.',
                    exception=exc,
                    context={
                        'name': name,
                        'email': email,
                        'subject': subject,
                    },
                )
                messages.error(request, 'We could not send your message right now. Please try again.')
            else:
                messages.success(request, 'Thanks. Your message has been sent and we’ll get back to you soon.')
                return render(request, 'pages/help_and_support.html', {
                    'show_turnstile': True,
                    'support_email': support_to,
                    'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
                })

    context = {
        'show_turnstile': True,
        'captcha_error': captcha_error,
        'support_email': 'admin@rentalution.co.uk',
        'TURNSTILE_SITE_KEY': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
    }
    if request.method == 'POST' and not captcha_error:
        context.update({
            'name': name,
            'email': email,
            'subject': subject,
            'message': message,
        })
    return render(request, 'pages/help_and_support.html', context)


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


def privacy_policy(request):
    return render(request, 'pages/privacy_policy.html')


def cookie_policy(request):
    return render(request, 'pages/cookie_policy.html')
