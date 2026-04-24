from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from .forms import LoginForm, UserRegistrationForm, ProfileImageForm, \
                    UserEditForm, ProfileEditForm, ProfileAddForm
from django.contrib.auth.decorators import login_required
from .models import Profile
from django.contrib import messages
from django.views import View
import logging
from django.http import JsonResponse
from .tasks import send_random_mail

from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from .tokens import account_activation_token
from django.contrib.auth.models import User
from django.urls import reverse


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
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        user_profile_form = ProfileAddForm(request.POST)
        if user_form.is_valid():
            new_user = user_form.save(commit=False)
            new_user.set_password(
                user_form.cleaned_data['password']
            )
            # create the user profile
            if user_profile_form.is_valid():
                new_user.is_active = False
                new_user.save()
                user_profile = user_profile_form.save(commit=False)
                user_profile.user = new_user
                user_profile.save()
                
                messages.success(request, 'New user created - please activate via email link')
    
                current_site = get_current_site(request)
                subject = 'Activate Your SharingHub Account'
                context = {
                    'new_user' : new_user
                }
                message = render_to_string('account_activation_email.html', {
                'user': new_user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(str(new_user.pk).encode()),
                # 'uid': str(new_user.pk),
                'token': account_activation_token.make_token(new_user),
                })
                new_user.email_user(subject, message)
                # send_random_mail.delay()
                
                return render(request,
                            'account/register_done.html',
                            context)
        #     else:
        #         messages.error(request, "You must be 18 to register")
        # # else:
        # #     if user_form['username'].errors:
        # #         messages.error(request, "Please choose another username {} ".format(user_form['username'].errors))
        # #     else:    
        # #         messages.error(request, "Please correct the highlighted items")

    else:
        user_form = UserRegistrationForm()
        user_profile_form = ProfileAddForm()
    context = {
        'user_form' : user_form,
        'user_profile_form' : user_profile_form
    }
    return render(request,
                'account/register.html',
                context)

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