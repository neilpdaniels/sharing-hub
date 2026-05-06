from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

# app_name='account'
urlpatterns = [
    # path('login/', views.user_login, name='login'),
    # path('login/', auth_views.LoginView.as_view(), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('password_change/', auth_views.PasswordChangeView.as_view(), 
    #     name='password_change'),
    # path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), 
    #     name='password_change_done'),
    # path('password_reset/', auth_views.PasswordResetView.as_view(),
    #     name='password_reset'),
    # path('password_reset/done', auth_views.PasswordResetDoneView.as_view(),
    #     name='password_reset_done'),
    # path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
    #     name='password_reset_confirm'),
    # path('reset/done/', auth_views.PasswordResetCompleteView.as_view(),
    #     name='password_reset_complete'),
    path('myaccount/', views.myaccount, name='myaccount'),
    path('mobile-verify/', views.mobile_verify, name='mobile_verify'),
    path('', include('django.contrib.auth.urls')),
    path('register/', views.register, name='register'),
    path('register/address-lookup/', views.address_lookup, name='address_lookup'),
    path('register/address-resolve/', views.address_resolve, name='address_resolve'),
    path('register/check-username/', views.check_username, name='check_username'),
    path('edit/' , views.edit, name='edit'),
    path('user_image_upload/', views.ProfileImageUpload.as_view(), name='user_image_upload'),
    path('account_activation_sent/', views.account_activation_sent, name='account_activation_sent'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate_account'),
    
]