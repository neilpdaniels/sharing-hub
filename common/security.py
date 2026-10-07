"""Security utilities for Turnstile CAPTCHA verification and token validation."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_turnstile_token(token, remote_ip='', *, expected_action):
    """
    Verify a Cloudflare Turnstile CAPTCHA token.

    Args:
        token (str): The Turnstile response token from the client
        remote_ip (str, optional): The client's remote IP address

    Returns:
        bool: True if token is valid, False otherwise
    """
    secret = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', '').strip()
    expected_hostnames = getattr(settings, 'TURNSTILE_HOSTNAMES', frozenset())
    if not secret or not expected_hostnames or not token or len(token) > 2048:
        logger.warning('Turnstile is not configured or supplied token is invalid.')
        return False

    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret,
                'response': token,
                'remoteip': remote_ip,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return bool(
            payload.get('success')
            and payload.get('action') == expected_action
            and (payload.get('hostname') or '').lower() in expected_hostnames
        )
    except Exception as exc:
        logger.warning('Turnstile verification failed: %s', exc)
        return False
