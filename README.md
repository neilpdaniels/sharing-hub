## Script and Wrapper Catalogue

Run these commands from the repository root unless stated otherwise. The scripts use the project virtual environment and project-local configuration where applicable.

### Application Launchers

| Script | Purpose | Usage |
| --- | --- | --- |
| `./run_rentalution` | Starts the local Django server and, when Celery is not eager, the Celery worker, Celery beat, and Flower. It can optionally start and configure Stripe CLI’s test webhook listener. Existing matching processes are stopped first. | `./run_rentalution` |
| `./run_rentalution_local` | Local Django/Celery launcher with the same current behavior as `run_rentalution`. | `./run_rentalution_local` |
| `./run_rentalution_mobile` | Starts the Flutter mobile app using the `dev` flavor. Displays a numbered device menu for connected USB Android devices, wireless Android devices, and Linux desktop. | `./run_rentalution_mobile` |
| `./run_rentalution_mobile_dev` | Starts the Flutter app using the `dev` flavor without a device menu. Loads `.rentalution_mobile.dev.env` when present and defaults to the MagicDNS host `neil-laptop` when `API_BASE_URL` is not set. | `./run_rentalution_mobile_dev` |
| `./run_rentalution_mobile_prod` | Starts the Flutter app using the `prod` flavor in release mode. Loads `.rentalution_mobile.prod.env` when present and defaults to `https://rentalution.co.uk/api/v1`. | `./run_rentalution_mobile_prod` |

### Mobile Wrappers

| Script | Purpose | Usage |
| --- | --- | --- |
| `./rentalution_mobile.local.sh` | Selects the mobile environment and delegates to the matching launcher. The default is `dev`. | `./rentalution_mobile.local.sh [dev|prod]` |
| `./run_flutter_local` | Convenience wrapper for `run_rentalution_mobile_dev`. | `./run_flutter_local` |

Examples:

```bash
./rentalution_mobile.local.sh dev
./rentalution_mobile.local.sh prod
./run_flutter_local
```

Mobile launchers require `STRIPE_CONNECT_PUBLIC_KEY`. The dev launcher also supports `APP_NAME` and `API_BASE_URL` through the environment or `.rentalution_mobile.dev.env`.

### Changing the local mobile API server without rebuilding

Both development launchers label the app as `Rentalution Dev`. In that app, tap
the **Server** button in the top-right, enter only the current laptop IP address
(for example `192.168.1.42`), save, then fully close and reopen the app. It
always connects to `http://address:8000/api/v1`. The address is stored on the
device and takes precedence over the build-time value, so no APK rebuild is
required after changing Wi-Fi or using a hotspot.

For the first install, `run_rentalution_mobile` and
`run_rentalution_mobile_dev` default to the MagicDNS hostname `neil-laptop` if
`API_BASE_URL` is unset. Override it from the environment or
`.rentalution_mobile.dev.env` when you need a different server.

### Stripe test webhooks

When launched interactively, `./run_rentalution` can start Stripe CLI before
Django starts. It reads the listener's generated `whsec_...` value and exports
it as `STRIPE_CONNECT_WEBHOOK_SECRET` for the Django server it launches; no
manual `.env` edit or restart is needed. The listener forwards the SetupIntent
events handled by the app (including lender `account.updated` status changes) to
`http://localhost:8000/transaction/stripe/connect/webhook/`, logs to
`logs/stripe_listen.log`, and is stopped when the launcher exits. The prompt is
skipped for non-interactive/automated runs. Run `stripe login` once before using
this option.

### Testing browser evidence QR codes locally

`./run_rentalution` and `./run_rentalution_local` automatically detect the
machine's LAN IP and use it for the evidence QR. A phone cannot reach
`127.0.0.1` on a developer machine. To override the detected IP with a stable
local hostname or an HTTPS tunnel URL, set the origin before starting it:

```bash
PHONE_EVIDENCE_BASE_URL=https://example-tunnel.example \
  ./run_rentalution
```

Use a stable local hostname such as `http://your-machine.local:8000` when
available. Both devices must be on the same network unless using a tunnel.

### Data and Deployment Helpers

| Script | Purpose | Usage |
| --- | --- | --- |
| `./run_seed_catalog_items` | Runs the Django `seed_catalog_items` management command using the local settings by default. | `./run_seed_catalog_items [options]` |
| `./run_seed_transaction_scenarios` | Opens a menu to seed missing scenarios, move existing scenarios to commence/finish today, or reset them. Date moves preserve rental length and workflow progress; production use is blocked. | `./run_seed_transaction_scenarios` |
| `./run_promote_product_drafts` | Runs the `promote_product_drafts` management command against the configured remote host. | `./run_promote_product_drafts [options]` |

Set `SETTINGS_MODULE` to override the default settings module used by the seed scripts.

The transaction scenario menu uses today's date in Europe/London and updates only recognised seeded transactions. It also updates their reserved dates. For automation, the script still accepts `--reset`, `--commence-today`, or `--finish-today` directly; the date options require existing scenarios and do not recreate them.

To add a rental ready for checkout evidence, run `./run_seed_transaction_scenarios --rental-ready` (menu option 8). This creates `scenario-rental-ready`, starting today for three rental days, with both test contracts confirmed. It creates a reusable Stripe test card and runs the application's verification authorization and cancellation before marking the card verified. Configure `STRIPE_CONNECT_SECRET_KEY` with a test key (`sk_test_` or `rk_test_`); live keys and production environments are rejected. The existing `scenario-checkout` remains available for testing manual card setup. This uses [Stripe's test token support](https://docs.stripe.com/api/payment_methods/create) and does not use a real card.

### Stripe Connect Sandbox matrix

With non-production `STRIPE_CONNECT_*` test credentials configured, first run `uv run python manage.py stripe_connect_matrix --webhooks`. It checks for the managed Stripe CLI listener and, if absent, asks before starting one. The listener writes its current `whsec_...` to a mode-600 runtime file shared with Django; do not copy it into source control. Then run `uv run python manage.py stripe_connect_matrix --execute --include-declines --webhooks`. It verifies 3-day, 7-day, 30-day, and 31-day deposit policies. Short/standard cases create and cancel a £1 test authorisation; the 31-day case captures then fully refunds £1, matching the long-rental policy. Decline coverage uses Stripe test tokens and creates no successful charge. The command refuses production and live keys.

Rerunning `--rental-ready` preserves existing verification, dates, and workflow progress. If Stripe verification fails, it exits with an error and leaves the scenario unverified for a retry. To move a previously created rental-ready scenario to today, use `--transaction-id ID --commence-today`. Rental payment and the full deposit are handled by the normal checkout flow; the seed only verifies the test card.

### Configuration and Environment Checks

| Script | Purpose | Usage |
| --- | --- | --- |
| `./scripts/check_db_env.sh` | Loads an environment file, prints database-related values with secrets masked, and optionally tests the database connection when `CHECK_DB_CONNECTION=1`. | `./scripts/check_db_env.sh [env-file]` |
| `./scripts/check_prod_env.sh` | Verifies that the required production environment variables are present. | `./scripts/check_prod_env.sh` |
| `./scripts/check_hardcoded_config.sh` | Searches tracked source/config file types for known hardcoded secrets or configuration values. | `./scripts/check_hardcoded_config.sh` |

Examples:

```bash
./scripts/check_db_env.sh .env
CHECK_DB_CONNECTION=1 ./scripts/check_db_env.sh .env
./scripts/check_prod_env.sh
./scripts/check_hardcoded_config.sh
```

todo




check connection through to transpact
-- createTRwansaction works
-- what about get trasnaction?
ViewPayeeTranspacts
ViewPayerTranspacts
--> test over soapui or similar - whats going wrong?



[2026-02-28 11:32:51,179: INFO/ForkPoolWorker-1] get user transactions
[2026-02-28 11:32:51,620: WARNING/ForkPoolWorker-1] running get transactions for user neil@sharing-hub.com
[2026-02-28 11:32:51,700: ERROR/ForkPoolWorker-1] <class 'NoneType'>
[2026-02-28 11:32:51,700: WARNING/ForkPoolWorker-1] running get transactions for user neil_p_daniels@hotmail.com
[2026-02-28 11:32:51,773: ERROR/ForkPoolWorker-1] <class 'NoneType'>
[2026-02-28 11:32:51,773: WARNING/ForkPoolWorker-1] running get transactions for user testuser2@sharing-hub.com
[2026-02-28 11:32:51,858: ERROR/ForkPoolWorker-1] <class 'NoneType'>

Video evidence now uses device-side upload compression, Celery-generated previews and full-upload downloads. See [video setup and deployment](docs/video_evidence.md).
