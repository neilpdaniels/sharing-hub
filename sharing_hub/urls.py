"""sharing_hub URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite
import navigation

# admin.site.__class__ = OTPAdminSite

urlpatterns = [
    # path('userRegistration/', include("userRegistration.urls")),
    path('site_cfg_admin/', admin.site.urls),
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path('account/', include('account.urls')),
    path('friends/', include('friends.urls', namespace='friends')),
    path('transaction/', include('transaction.urls', namespace='transaction')),
    path('navigation/', include('navigation.urls', namespace='navigation')),
    path('my_sharing_hub/', include('my_sharing_hub.urls', namespace='my_sharing_hub')),
    path('', navigation.views.index, name='homepage'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                        document_root=settings.MEDIA_ROOT)
    
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns