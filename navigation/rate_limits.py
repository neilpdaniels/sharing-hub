"""Low-cost, fail-closed limits for category-suggestion submissions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from ipaddress import ip_address

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from common.failures import record_site_failure


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    message: str = ''


def client_ip(request) -> str:
    """Read Nginx's overwritten real-IP header, with a safe direct fallback.

    Production binds Gunicorn only to localhost, so external clients cannot
    reach Django directly and forge this header. Nginx sets it from its socket
    peer address in ``deploy/nginx/rentalution.conf``.
    """
    value = (request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR') or '').strip()
    try:
        return str(ip_address(value))
    except ValueError:
        return 'unknown'


def _period_key(name: str, value: str, period_start, timeout: int) -> tuple[str, int]:
    return (f'category-ai:{name}:{value}:{period_start:%Y%m%d%H}', timeout)


def _consume(key: str, timeout: int, limit: int) -> bool:
    """Use Redis add/incr atomically enough for a fixed-window quota.

    Any cache failure rejects the request: availability must never turn into a
    path for unbounded paid AI work.
    """
    try:
        if cache.add(key, 1, timeout=timeout):
            return True
        return int(cache.incr(key)) <= limit
    except Exception:
        return False


def _alert_once(key: str, message: str, context: dict[str, str]) -> None:
    """Alert staff about unusual volume without sending one email per request."""
    try:
        if cache.add(f'{key}:alerted', 1, timeout=60 * 60):
            record_site_failure('Category suggestion rate limit reached', details=message, context=context)
    except Exception:
        # The form must retain its fail-closed behaviour even if admin alerting
        # is temporarily unavailable.
        return


def consume_submission_quota(request) -> LimitResult:
    now = timezone.now()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    user_id = str(request.user.pk)
    ip = client_ip(request)
    limits = (
        ('user-week', user_id, week_start, 8 * 24 * 60 * 60, settings.CATEGORY_AI_USER_WEEKLY_LIMIT,
         'You have reached this week’s category suggestion limit. Please try again next week.'),
        ('user-month', user_id, month_start, 32 * 24 * 60 * 60, settings.CATEGORY_AI_USER_MONTHLY_LIMIT,
         'You have reached this month’s category suggestion limit. Please try again next month.'),
        ('ip-day', ip, day_start, 26 * 60 * 60, settings.CATEGORY_AI_IP_DAILY_LIMIT,
         'Too many category suggestions have been submitted from this connection today. Please try again tomorrow.'),
    )
    for name, value, start, timeout, limit, message in limits:
        key, ttl = _period_key(name, value, start, timeout)
        if not _consume(key, ttl, limit):
            _alert_once(key, message, {'limit': name, 'value': value})
            return LimitResult(False, message)
    return LimitResult(True)
