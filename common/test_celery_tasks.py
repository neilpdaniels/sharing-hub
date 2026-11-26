from unittest.mock import Mock

from celery.exceptions import Retry
from django.db import OperationalError
from django.test import SimpleTestCase

from common.celery_tasks import SCHEDULED_TASK_RETRY_DELAYS, scheduled_task


class ScheduledTaskRetryTests(SimpleTestCase):
    def _failing_task(self):
        @scheduled_task(name='common.tests.retrying_database_task')
        def task():
            raise OperationalError('could not translate host name "db" to address')

        return task

    def test_retries_database_connectivity_with_the_configured_delays(self):
        task = self._failing_task()

        for attempt, delay in enumerate(SCHEDULED_TASK_RETRY_DELAYS):
            retry = Mock(side_effect=Retry())
            task.retry = retry
            task.push_request(retries=attempt)
            try:
                with self.assertRaises(Retry):
                    task.run()
            finally:
                task.pop_request()

            retry.assert_called_once()
            retry_args = retry.call_args.kwargs
            self.assertEqual(retry_args['countdown'], delay)
            self.assertEqual(
                retry_args['max_retries'], len(SCHEDULED_TASK_RETRY_DELAYS)
            )
            self.assertIsInstance(retry_args['exc'], OperationalError)

    def test_reraises_database_error_after_the_last_retry(self):
        task = self._failing_task()
        task.retry = Mock()
        task.push_request(retries=len(SCHEDULED_TASK_RETRY_DELAYS))
        try:
            with self.assertRaises(OperationalError):
                task.run()
        finally:
            task.pop_request()

        task.retry.assert_not_called()

    def test_does_not_retry_a_non_connectivity_database_error(self):
        @scheduled_task(name='common.tests.non_retrying_database_task')
        def task():
            raise OperationalError('relation "missing_table" does not exist')

        task.retry = Mock()
        with self.assertRaises(OperationalError):
            task.run()

        task.retry.assert_not_called()
