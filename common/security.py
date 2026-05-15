"""Security utilities for Turnstile CAPTCHA verification and token validation."""

import json
import logging
import urllib.parse
import urllib.request

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_turnstile_token(token, remote_ip=''):
    """
    Verify a Cloudflare Turnstile CAPTCHA token.

    Args:
        token (str): The Turnstile response token from the client
        remote_ip (str, optional): The client's remote IP address

    Returns:
        bool: True if token is valid, False otherwise
    """
    secret = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', '')
    if not secret:
        # Skip validation if secret key not configured
        return True
    if not token:
        return False

    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret,
                'response': token,
                'remoteip': remote_ip,
            },
            timeout=5,
        )
        payload = response.json()
        return bool(payload.get('success'))
    except Exception as exc:
        logger.warning('Turnstile verification failed: %s', exc)
        return False
