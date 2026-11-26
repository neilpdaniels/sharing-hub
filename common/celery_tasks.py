"""Common Celery task behaviour for jobs dispatched by Celery Beat."""

from functools import wraps

from celery import shared_task
from django.db import InterfaceError, OperationalError


# The first recovery attempt is deliberately immediate.  The following retries
# give Docker's embedded DNS and a restarting PostgreSQL container enough time
# to recover without silently losing a scheduled job.
SCHEDULED_TASK_RETRY_DELAYS = (0, 5, 10, 30)


# These are the connection failures PostgreSQL/psycopg report while Docker
# networking, DNS, or the database process is briefly unavailable.  Keeping
# this deliberately narrow avoids retrying permanent database mistakes (for
# example, an invalid query or a missing migration).
_TRANSIENT_DATABASE_CONNECTION_MARKERS = (
    "could not translate host name",
    "temporary failure in name resolution",
    "could not resolve",
    "could not connect to server",
    "connection refused",
    "connection reset",
    "connection timed out",
    "timeout expired",
    "server closed the connection",
    "connection already closed",
    "connection is closed",
    "database system is starting up",
    "database system is in recovery mode",
    "database is not accepting connections",
    "the database system is starting up",
    "ssl connection has been closed",
)


def _is_transient_database_connection_error(error):
    """Return whether *error* represents a short-lived database outage."""
    message = str(error).lower()
    return any(marker in message for marker in _TRANSIENT_DATABASE_CONNECTION_MARKERS)


def scheduled_task(**task_options):
    """Create a Beat-safe task that retries transient database connectivity.

    Scheduled work must not be lost merely because a container cannot resolve
    the ``db`` service for a few seconds.  Only connection-style database
    errors are retried: query/schema errors should still fail immediately and
    remain visible to operators.
    """

    def decorate(function):
        @shared_task(bind=True, **task_options)
        @wraps(function)
        def runner(self, *args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (OperationalError, InterfaceError) as exc:
                if not _is_transient_database_connection_error(exc):
                    raise
                retries = self.request.retries
                if retries >= len(SCHEDULED_TASK_RETRY_DELAYS):
                    raise
                raise self.retry(
                    exc=exc,
                    countdown=SCHEDULED_TASK_RETRY_DELAYS[retries],
                    max_retries=len(SCHEDULED_TASK_RETRY_DELAYS),
                )

        # Makes the retry policy easy to audit without relying on Celery's
        # internals or parsing task decorators.
        runner.scheduled_retry_delays = SCHEDULED_TASK_RETRY_DELAYS
        return runner

    return decorate
