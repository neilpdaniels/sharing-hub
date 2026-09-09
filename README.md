## Script and Wrapper Catalogue

Run these commands from the repository root unless stated otherwise. The scripts use the project virtual environment and project-local configuration where applicable.

### Application Launchers

| Script | Purpose | Usage |
| --- | --- | --- |
| `./run_rentalution` | Starts the local Django server and, when Celery is not eager, the Celery worker, Celery beat, and Flower. Existing matching processes are stopped first. | `./run_rentalution` |
| `./run_rentalution_local` | Local Django/Celery launcher with the same current behavior as `run_rentalution`. | `./run_rentalution_local` |
| `./run_rentalution_mobile` | Starts the Flutter mobile app using the `dev` flavor. Displays a numbered device menu for connected USB Android devices, wireless Android devices, and Linux desktop. | `./run_rentalution_mobile` |
| `./run_rentalution_mobile_dev` | Starts the Flutter app using the `dev` flavor without a device menu. Loads `.rentalution_mobile.dev.env` when present and detects a LAN API address when `API_BASE_URL` is not set. | `./run_rentalution_mobile_dev` |
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

### Data and Deployment Helpers

| Script | Purpose | Usage |
| --- | --- | --- |
| `./run_seed_catalog_items` | Runs the Django `seed_catalog_items` management command using the local settings by default. | `./run_seed_catalog_items [options]` |
| `./run_seed_transaction_scenarios` | Opens a menu to seed missing scenarios, move existing scenarios to commence/finish today, or reset them. Date moves preserve rental length and workflow progress; production use is blocked. | `./run_seed_transaction_scenarios` |
| `./run_promote_product_drafts` | Runs the `promote_product_drafts` management command against the configured remote host. | `./run_promote_product_drafts [options]` |

Set `SETTINGS_MODULE` to override the default settings module used by the seed scripts.

The transaction scenario menu uses today's date in Europe/London and updates only recognised seeded transactions. It also updates their reserved dates. For automation, the script still accepts `--reset`, `--commence-today`, or `--finish-today` directly; the date options require existing scenarios and do not recreate them.

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
