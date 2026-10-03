# Production Celery and Flower TODO

## Current state

- The production VPS has `POSTGRES_HOST=db`, `POSTGRES_PORT=5432`, `FCM_SENDER_ID=938503213951`, and `FLOWER_BASIC_AUTH` configured in `/srv/rentalution/.env`.
- Docker disk cleanup reclaimed 1.566 GB; the last deployment then reached the production-environment check.
- Local changes are intentionally uncommitted: `docker-compose.prod.yml` adds `worker`, `beat`, and private `flower`; `scripts/check_prod_env.sh` now requires `FLOWER_BASIC_AUTH`; `.env.example` documents it; the deployment workflow waits for all services and verifies both workers and Flower before updating Nginx.
- Current production has web, PostgreSQL, and Redis running. It does not currently have a general Celery worker, Celery Beat, or Flower.

## Before committing

- Review the uncommitted diff: `git diff -- docker-compose.prod.yml scripts/check_prod_env.sh .env.example`.
- Keep one Beat service only. It schedules expiry, reminders, feedback closure, and overdue-booking jobs; multiple Beat instances can duplicate that work.
- The worker containers use Celery process autoscaling: the general worker runs 1–4 processes and the video worker runs 1–2. These are deliberately conservative limits; do not raise them until CPU, memory, queue depth, and task latency have been observed on the VPS. Beat and Flower remain single-instance services.

## Deploy

```bash
git add .github/workflows/ci-cd.yml docker-compose.prod.yml scripts/check_prod_env.sh .env.example docs/production-celery-flower-todo.md
git commit -m "Run Celery workers, Beat, and private Flower in production"
git push
```

The GitHub Actions deployment starts the new services, waits for `web`, PostgreSQL, Redis, both workers, Beat, and Flower to stay running, verifies Celery ping for both workers, and confirms that Flower is responding before updating Nginx.

## Verify on the VPS after deployment

```bash
cd /srv/rentalution
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 worker beat video-worker flower
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec worker sh scripts/check_celery_runtime.sh
```

Expected running services: `web`, `db`, `redis`, `worker`, `video-worker`, `beat`, and `flower`.

## Access Flower privately

Flower is bound only to the VPS loopback interface, `127.0.0.1:5555`; it is not publicly exposed.

```bash
ssh -L 5555:127.0.0.1:5555 ubuntu@your-vps
```

Open `http://localhost:5555` and sign in using the credentials stored in `FLOWER_BASIC_AUTH` on the VPS.

## Launch acceptance checks

- Confirm one registration email, one push notification, and one non-destructive background task complete.
- Confirm the worker and video worker answer Celery ping.
- Confirm Beat stays running through at least one minute and produces scheduled-task log activity.
- Before enabling customer live payments, run the planned Stripe/Connect test matrix in staging and reconcile results with Stripe.
