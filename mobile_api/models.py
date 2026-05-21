from django.conf import settings
from django.db import models


class MobileDevice(models.Model):
    PLATFORM_ANDROID = 'android'
    PLATFORM_IOS = 'ios'
    PLATFORM_WEB = 'web'
    PLATFORM_OTHER = 'other'

    PLATFORM_CHOICES = (
        (PLATFORM_ANDROID, 'Android'),
        (PLATFORM_IOS, 'iOS'),
        (PLATFORM_WEB, 'Web'),
        (PLATFORM_OTHER, 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='mobile_devices',
        on_delete=models.CASCADE,
    )
    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default=PLATFORM_OTHER)
    device_id = models.CharField(max_length=120, blank=True, default='')
    app_version = models.CharField(max_length=32, blank=True, default='')
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated',)

    def __str__(self):
        return f'{self.user_id}:{self.platform}:{self.token[:16]}'
