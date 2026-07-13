# Commands Reference

This document lists the wrapper scripts and deployment-related commands in the repo, grouped by what they do.

## Local Wrapper Scripts

### `run_rentalution`

Starts the local development stack:

- activates the project virtualenv
- sets `DJANGO_SETTINGS_MODULE=rentalution.settings.local`
- stops existing Celery / runserver processes
- starts Celery worker, beat, and Flower unless `CELERY_TASK_ALWAYS_EAGER=True`
- starts Django on `0.0.0.0:8000`

Useful when you want the full local app running with background tasks.

### `run_rentalution_local`

Same pattern as `run_rentalution` for local development.

### `run_seed_catalog_items`

Runs the catalog seed command with local settings:

```bash
uv run python manage.py seed_catalog_items --settings=rentalution.settings.local
```

Use this to load or refresh catalog categories and products in dev.

### `run_seed_transaction_scenarios`

Seeds transaction test scenarios with local settings by default.

Optional `--reset` is blocked in production by the script.

### `run_promote_product_drafts`

Wrapper for the product draft promotion flow.

It calls:

```bash
uv run python manage.py promote_product_drafts --host 51.89.165.49 --user ubuntu
```

You pass additional promotion flags after that.

### Image creation GUI

There is no separate wrapper script for the image GUI. Launch it directly with:

```bash
uv run python manage.py midjourney_image_gui
```

Useful flags:

```bash
uv run python manage.py midjourney_image_gui --refresh
uv run python manage.py midjourney_image_gui --reset
```

Notes:

- It uses `tkinter`, so it needs a desktop session and a working GUI display.
- The window is for the Midjourney/OpenAI image workflow, including prompt editing, generation, and review.

## Deployment Commands

### GitHub Actions deploy

See [DEPLOY_GITHUB_ACTIONS.md](../DEPLOY_GITHUB_ACTIONS.md).

Core production workflow:

```bash
git push origin main
```

The workflow:

- runs `python manage.py check`
- builds and pushes the Docker image
- pulls the new image on the server
- runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### Hetzner / Docker deploy

See [DEPLOY_HETZNER_DOCKER.md](../DEPLOY_HETZNER_DOCKER.md).

First-time server startup:

```bash
docker compose up -d --build
```

### Production app restart / update

Used on the server after pulling code or a new image:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Production migrations and seed

Typical production data refresh sequence:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web uv run python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web uv run python manage.py seed_catalog_items
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T web uv run python manage.py rebuild_summary_prices
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate web
```

## Management Commands

These are the underlying Django commands used by the scripts above.

### Catalog and images

- `seed_catalog_items`
- `export_catalog_image_bundle`
- `export_catalog_image_links`
- `import_catalog_image_links`
- `export_midjourney_category_prompts`
- `rebuild_summary_prices`

### Product draft workflow

- `export_product_draft_bundle`
- `import_product_draft_bundle`
- `promote_product_drafts`

### Transaction scenarios

- `seed_transaction_scenarios`

## Environment Checks

### `scripts/check_prod_env.sh`

Checks that the expected production environment variables are present.

Example:

```bash
sh scripts/check_prod_env.sh
```

### `scripts/check_db_env.sh`

Loads an env file and prints masked database-related values.

Example:

```bash
sh scripts/check_db_env.sh .env
```

To test the DB connection too:

```bash
CHECK_DB_CONNECTION=1 sh scripts/check_db_env.sh .env
```

## Common Workflows

### Load catalog into dev

```bash
./run_seed_catalog_items
```

### Start local app

```bash
./run_rentalution
```

### Promote ready product drafts

```bash
./run_promote_product_drafts --all-ready --target dev
```

### Seed transactions for local testing

```bash
./run_seed_transaction_scenarios
```

## Notes

- Wrapper scripts live at the repo root.
- Deployment scripts usually call Docker Compose on the server.
- Product images are best handled through the staged product draft flow when you want to move a listing from draft to live in a controlled way.
