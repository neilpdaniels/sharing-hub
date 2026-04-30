from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from .forms import LoginForm, UserRegistrationStartForm, UserRegistrationVerifyForm, ProfileImageForm, \
                    UserEditForm, ProfileEditForm, ProfileAddForm
from django.contrib.auth.decorators import login_required
from .models import Profile, RegistrationVerification
from django.contrib import messages
from django.views import View
import logging
from django.http import JsonResponse
from .tasks import send_random_mail
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from random import randint
import requests

from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from .tokens import account_activation_token
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings


logger = logging.getLogger(__name__)


# def user_login(request):
#     if request.method == 'POST':
#         form = LoginForm(request.POST)
#         if form.is_valid():
#             cd = form.cleaned_data
#             user = authenticate(request,
#                                 username=cd['username'],
#                                 password=cd['password'])
#             if user is not None:
#                 if user.is_active:
#                     login(request, user)
#                     return HttpResponse('Authenticated OK')
#                 else:
#                     return HttpResponse('Disabled account')
#             else:
#                 return HttpResponse('Invalid login')
#     else:
#         form = LoginForm()

#     context = {
#         'form' : form
#     }
#     return render(request, 'account/login.html', context)


@login_required
def myaccount(request):
    context = {
        'section' : 'dashboard',
    }
    return render(request,
                'account/dashboard.html',
                context)

def register(request):
    def generate_unique_verification_code():
        for _ in range(20):
            code = f"{randint(0, 999999):06d}"
            if not RegistrationVerification.objects.filter(verification_code=code, is_used=False).exists():
                return code
        raise ValueError('Could not generate a unique verification code.')

    stage = 'start'
    user_form = UserRegistrationStartForm()
    verify_form = UserRegistrationVerifyForm()
    verify_email = request.session.get('pending_registration_email', '')

    if request.method == 'POST':
        action = request.POST.get('action', 'start')

        if action == 'start':
            user_form = UserRegistrationStartForm(request.POST)
            if user_form.is_valid():
                # Verify Cloudflare Turnstile token
                import urllib.request
                import urllib.parse
                import json as _json
                from django.conf import settings as _settings
                _token = request.POST.get('cf-turnstile-response', '')
                _secret = _settings.CLOUDFLARE_TURNSTILE_SECRET_KEY
                _data = urllib.parse.urlencode({'secret': _secret, 'response': _token, 'remoteip': request.META.get('REMOTE_ADDR', '')}).encode()
                try:
                    _req = urllib.request.Request('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=_data)
                    _resp = _json.loads(urllib.request.urlopen(_req, timeout=5).read())
                    _turnstile_ok = _resp.get('success', False)
                except Exception:
                    _turnstile_ok = False
                if not _turnstile_ok:
                    messages.error(request, 'Human verification failed. Please try again.')
                else:
                    email = user_form.cleaned_data['email']
                    code = generate_unique_verification_code()

                    RegistrationVerification.objects.filter(email__iexact=email, is_used=False).delete()
                    RegistrationVerification.objects.create(
                        email=email,
                        first_name=user_form.cleaned_data['name'],
                        last_name='',
                        date_of_birth=user_form.cleaned_data['date_of_birth'],
                        mobile_number=user_form.cleaned_data['mobile_number'],
                        house_name_number=user_form.cleaned_data.get('house_name_number', ''),
                        address_line_1=user_form.cleaned_data['address_line_1'],
                        address_line_2=user_form.cleaned_data.get('address_line_2', ''),
                        town=user_form.cleaned_data['town'],
                        county=user_form.cleaned_data.get('county', ''),
                        postcode=user_form.cleaned_data['postcode'],
                        verification_code=code,
                        expires_at=timezone.now() + timedelta(minutes=15),
                    )

                    send_mail(
                        subject='Your SharingHub verification code',
                        message=(
                            'Your SharingHub registration code is: ' + code + '\n\n'
                            'This code expires in 15 minutes.'
                        ),
                        from_email=None,
                        recipient_list=[email],
                        fail_silently=False,
                    )

                    request.session['pending_registration_email'] = email
                    verify_email = email
                    stage = 'verify'
                    messages.success(request, 'We sent a 6-digit code to your email. Enter it and then set your password.')

        elif action == 'verify':
            verify_form = UserRegistrationVerifyForm(request.POST)
            stage = 'verify'
            verify_email = request.session.get('pending_registration_email', '')

            if not verify_email:
                messages.error(request, 'Verification session expired. Please start registration again.')
                stage = 'start'
                user_form = UserRegistrationStartForm()
            elif verify_form.is_valid():
                verification = RegistrationVerification.objects.filter(
                    email__iexact=verify_email,
                    is_used=False,
                ).order_by('-created_at').first()

                if verification is None:
                    messages.error(request, 'No pending verification found. Please start again.')
                    stage = 'start'
                    user_form = UserRegistrationStartForm()
                elif verification.is_expired:
                    verification.delete()
                    messages.error(request, 'Verification code expired. Please request a new code.')
                    stage = 'start'
                    user_form = UserRegistrationStartForm()
                elif verification.verification_code != verify_form.cleaned_data['verification_code']:
                    messages.error(request, 'Invalid verification code.')
                elif User.objects.filter(email__iexact=verify_email).exists():
                    messages.error(request, 'This email address is already registered.')
                    stage = 'start'
                    user_form = UserRegistrationStartForm()
                else:
                    new_user = User.objects.create(
                        username=verify_email,
                        email=verify_email,
                        first_name=verification.first_name,
                        last_name='',  # full name stored in first_name
                        is_active=True,
                    )
                    new_user.set_password(verify_form.cleaned_data['password'])
                    new_user.save()

                    Profile.objects.create(
                        user=new_user,
                        email_confirmed=True,
                        date_of_birth=verification.date_of_birth,
                        mobile_number=verification.mobile_number,
                        address_line_1=verification.address_line_1,
                        address_line_2=verification.address_line_2,
                        town=verification.town,
                        county=verification.county,
                        postcode=verification.postcode,
                    )

                    verification.is_used = True
                    verification.save(update_fields=['is_used', 'updated_at'])
                    request.session.pop('pending_registration_email', None)

                    login(request, new_user)
                    messages.success(request, 'Registration complete and email verified.')
                    return redirect(reverse('navigation:browseCategory', args=('metals', )))

    context = {
        'user_form': user_form,
        'verify_form': verify_form,
        'register_stage': stage,
        'verify_email': verify_email,
    }
    return render(request, 'account/register.html', context)

@login_required
def edit(request):
    if request.method=='POST':
        user_form = UserEditForm(instance=request.user, 
                                data=request.POST)
        profile_form = ProfileEditForm(instance=request.user.profile,
                                        data=request.POST,
                                        files=request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            messages.success(request, 'Profile updates saved')
            user_form.save()
            profile_form.save()
        else:
            messages.error(request, 'Profile updates not saved')

    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = ProfileEditForm(instance=request.user.profile)

    context = {
        'user_form' : user_form,
        'profile_form' : profile_form
    }
    return render(request, 'account/edit.html', context)

    
class ProfileImageUpload(View):
    def post(self, request):
        # logger = logging.getLogger(__name__)
        data = {'is_valid': False}
        form = ProfileImageForm(self.request.POST, self.request.FILES)
        if form.is_valid() and request.user is not None:
            try:
                user_profile = Profile.objects.get(user=request.user)
                user_profile.image = form.cleaned_data['image']
                user_profile.saveWithImage()
                # image = form.save(commit=False)
                # image.user = request.user
                # image.save()
                data = {'is_valid': True,
                        'image_name': user_profile.image.name, 
                        'image_url': user_profile.image.url}
            except Profile.DoesNotExist:
                pass
        else:
            data = {'is_valid': False}
        return JsonResponse(data)


def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.profile.email_confirmed = True
        user.save()
        user.profile.save()
        login(request, user)
        product_url = request.build_absolute_uri(reverse('navigation:browseCategory', args=('metals', )))
        return redirect(product_url)
    else:
        return render(request, 'account_activation_invalid.html')


def account_activation_sent(request):
    return render(request, 'account_activation_sent.html')


def _parse_getaddress_result(data):
    house_parts = [
        (data.get('sub_building_name') or '').strip(),
        (data.get('building_name') or '').strip(),
    ]
    building_number = (data.get('building_number') or '').strip()
    if building_number:
        house_parts.append(building_number)
    house_name_number = ' '.join(part for part in house_parts if part).strip()

    return {
        'house_name_number': house_name_number,
        'street_name': (data.get('thoroughfare') or '').strip(),
        'address_line_1': (data.get('line_1') or '').strip(),
        'address_line_2': (data.get('line_2') or '').strip(),
        'town': (data.get('town_or_city') or '').strip(),
        'county': (data.get('county') or '').strip(),
        'postcode': (data.get('postcode') or '').strip(),
    }


def _nominatim_lookup(query):
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': query,
                'countrycodes': 'gb',
                'format': 'json',
                'addressdetails': 1,
                'limit': 6,
            },
            headers={'User-Agent': 'SharingHub/1.0'},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    results = []
    for item in data:
        address = item.get('address', {})
        is_postcode_result = item.get('type') == 'postcode' or item.get('addresstype') == 'postcode'
        premise = (
            address.get('house')
            or address.get('building')
            or address.get('farm')
            or address.get('amenity')
            or address.get('name')
            or ('' if is_postcode_result else item.get('name'))
            or ''
        ).strip()
        house_number = (address.get('house_number') or '').strip()
        road = (address.get('road') or '').strip()

        line1_parts = []
        seen_parts = set()

        def add_part(value):
            value = (value or '').strip()
            if not value:
                return
            key = value.lower()
            if key in seen_parts:
                return
            seen_parts.add(key)
            line1_parts.append(value)

        add_part(premise)
        add_part(house_number)
        add_part(road)

        line1 = ' '.join(line1_parts).strip()
        if not line1 and not is_postcode_result:
            line1 = address.get('neighbourhood') or address.get('suburb') or item.get('display_name', '').split(',')[0].strip()

        results.append({
            'display': item.get('display_name', ''),
            'provider': 'nominatim',
            'house_name_number': premise or house_number,
            'street_name': road or line1,
            'address_line_1': line1,
            'address_line_2': '',
            'town': address.get('city') or address.get('town') or address.get('village') or '',
            'county': address.get('county') or address.get('state_district') or '',
            'postcode': address.get('postcode') or '',
        })

    return results


def address_lookup(request):
    query = (request.GET.get('q') or '').strip()
    if len(query) < 3:
        return JsonResponse({'results': []})

    api_key = getattr(settings, 'GETADDRESS_IO_API_KEY', '')
    if api_key:
        try:
            response = requests.get(
                f'https://api.getAddress.io/autocomplete/{query}',
                params={'api-key': api_key, 'all': 'true', 'top': 6},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                results = [
                    {
                        'display': suggestion.get('address', ''),
                        'provider': 'getaddress',
                        'id': suggestion.get('id', ''),
                    }
                    for suggestion in data.get('suggestions', [])
                    if suggestion.get('id')
                ]
                if results:
                    return JsonResponse({'results': results})
            else:
                logger.warning('getAddress autocomplete failed with status %s', response.status_code)
        except Exception as exc:
            logger.warning('getAddress autocomplete failed: %s', exc)

    return JsonResponse({'results': _nominatim_lookup(query)})


def address_resolve(request):
    address_id = (request.GET.get('id') or '').strip()
    if not address_id:
        return JsonResponse({'result': None})

    api_key = getattr(settings, 'GETADDRESS_IO_API_KEY', '')
    if api_key:
        try:
            response = requests.get(
                f'https://api.getAddress.io/get/{address_id}',
                params={'api-key': api_key},
                timeout=5,
            )
            if response.status_code == 200:
                return JsonResponse({'result': _parse_getaddress_result(response.json())})
            logger.warning('getAddress resolve failed with status %s', response.status_code)
        except Exception as exc:
            logger.warning('getAddress resolve failed: %s', exc)

    return JsonResponse({'result': None})