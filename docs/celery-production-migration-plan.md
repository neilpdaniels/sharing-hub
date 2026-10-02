# Celery production migration plan

## Why this is required

`docker-compose.prod.yml` currently starts only a `video-worker`, listening to the `video` queue. All tasks without an explicit queue use Celery's default `celery` queue, so they will be published but have no production consumer. No Celery Beat service is started either, so scheduled workflow tasks do not run.

The payment reporting pages are independent of Celery and can be enabled for staff in production. Payment execution must not be enabled for customers until the default worker and Beat are verified in staging.

## Security action required before deployment

The Transpact partner credentials that were previously committed in settings have been moved to environment variables. Rotate that password/credential with Transpact before any deployment: source removal does not remove a value from Git history. Store the replacement only in the production secret store as `TRANSPACT_PARTNER_USERNAME` and `TRANSPACT_PARTNER_PASSWORD`.

## Current task inventory

### Default queue: customer and payment-critical

- `transaction.tasks.async_confirm_card_setup` — confirms Stripe SetupIntent and verification hold.
- `transaction.tasks.async_setup_deposit_card_and_test_hold` — legacy/manual card verification path.
- `transaction.tasks.async_collect_deposit_hold` — creates the deposit authorisation/charge.
- `transaction.tasks.async_resolve_deposit_hold` — releases, captures, or refunds the deposit, then initiates the award transfer.
- `transaction.tasks.async_transfer_rental_proceeds` — transfers rental plus delivery proceeds to the lender.
- `transaction.tasks.async_retry_stripe_settlement` — staff-triggered retry of a failed lender transfer.
- `account.tasks.send_registration_verification_email` — registration email.
- `transaction.tasks.send_new_message_push_notification` — FCM message/enquiry notification.

### Default queue: application work

- `account.tasks.process_profile_image` — avatar image conversion.
- `transaction.tasks.process_transaction_message_image` — transaction-message image conversion.
- `common.tasks.updateSummaryPrices` — best-price summary refresh after an order changes.
- The former `getUserTransactions` and `createNewTransaction` placeholders and their dispatches have been removed; they performed no work and should be reintroduced only with a defined provider-sync requirement.
- `account.tasks.send_random_mail`, `common.tasks.runStaticMigration`, and `common.tasks.listEmptyCategories` — development/maintenance tasks; do not schedule or expose in production without an owner and runbook.

### `video` queue: already provisioned

- `transaction.tasks.generate_video_preview` — evidence-video preview/transcode. The current `video-worker` is correctly dedicated to this queue.

### Celery Beat schedules: currently not provisioned

- Every minute: `transaction.tasks.expireOrders`.
- Hourly at :15: `auto_close_feedback_windows`.
- Daily at 00:10: `auto_cancel_overdue_first_day_bookings`.
- Hourly at :05: `send_pending_action_reminders`.
- `escalate_overdue_disputes` exists but is not scheduled; decide its SLA cadence and add it deliberately.

## Migration plan

1. **Done in Compose:** add a `worker` service for the default `celery` queue, initially with concurrency 2. Do not run payment tasks in the video worker.
2. **Done in Compose:** add exactly one `beat` service using `celery -A rentalution beat --loglevel=info`, with a persistent schedule file. Beat must remain singleton: two instances send duplicate reminders and expiry work.
3. **Done in Compose:** keep the dedicated `video-worker` on the `video` queue. Add resource limits before launch.
4. **Partially done:** Redis now uses append-only persistence and a named volume. Define backup/failover expectations and verify an unplanned restart cannot silently drop queued payment work.
5. **Done in code:** classify tasks into `payments`, `notifications`, `maintenance`, and `video` queues. The worker consumes each non-video queue while keeping the existing `celery` queue for third-party/legacy tasks.
6. **Partially done:** payment tasks use late acknowledgement and worker-loss rejection with a 120-second limit, so a worker crash redelivers work and Stripe idempotency keys make replay safe. Add bounded retries only after classifying Stripe failures as transient versus business/card failures; do not retry declines automatically.
7. **Partially done:** Docker health checks now cover Redis, both workers, and Beat. Add external alerts for worker heartbeat, queue depth, oldest-message age, task failure rate, and Beat last-run time. Add a runbook for replaying a failed settlement through the existing staff retry control.
8. **Done in deployment workflow:** migrations and static collection now run before web, worker, and Beat containers start. The deploy job waits for the default worker and Beat to respond before updating Nginx.
9. In staging, publish one task from each class, verify the correct worker consumes it, then run the Stripe test matrix including webhooks and declines. Verify the payment ledger and Stripe Dashboard agree after each case.
10. Release in this order: Redis/monitoring, default worker, Beat, then customer payment actions. Keep the video worker untouched. Observe queues and payment attempts before enabling live Stripe keys.

## Production acceptance checks

- `scripts/check_prod_env.sh` passes with `ENVIRONMENT_NAME=Production` and live Stripe keys; it rejects test keys.
- `celery -A rentalution inspect ping` returns the default worker and the video worker.
- Beat logs each expected schedule at its configured cadence.
- A registration email, push notification, card setup, deposit hold, rental transfer, and deposit settlement each complete in staging.
- Restart the default worker during a non-destructive staging task and confirm it is retried/observable.
- Stripe webhook delivery is successful and the payment/settlement ledger reconciles to Stripe.
- No default-queue message remains unconsumed beyond the agreed alert threshold.

## Staging execution runbook

Run these only against a non-production deployment with Stripe test credentials:

1. Deploy the image and confirm `docker compose ... ps` reports `web`, `worker`, `beat`, and `video-worker` as running/healthy.
2. From the worker container, run `sh scripts/check_celery_runtime.sh`; confirm the default worker answers `pong`. Confirm the Beat container remains healthy for at least one scheduled interval.
3. Create a registration verification request, transaction message, profile image, and evidence video. Confirm each reaches its intended queue and completes.
4. Run `uv run python manage.py stripe_connect_matrix --execute --include-declines --webhooks`; confirm all 3/7/30/31-day policies and decline handling pass.
5. Run each lifecycle outcome separately: `full-release`, `partial-award`, and `fee-shortfall`. The runner resets its seeded data each time, so record the Stripe IDs and reconcile each result before starting the next case.
6. Confirm the admin payment ledger, Rentalution payments ledger, and Stripe Dashboard agree on renter charge, lender transfer, service fee, deposit release/award, and Stripe fee.
7. Restart the default worker while a harmless staging notification task is queued. Confirm it is redelivered or produces an observable failure; do not simulate this with a live payment task.
8. Configure infrastructure alerts for the Docker health checks, worker queue depth, oldest message age, task failures, and Beat absence before changing to live Stripe keys.
