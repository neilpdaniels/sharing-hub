# GitHub Actions Deploy

## Required GitHub Secrets

- `DEPLOY_HOST` - the server IP or hostname
- `DEPLOY_USER` - the SSH user, usually `ubuntu`
- `DEPLOY_SSH_KEY` - the private SSH key GitHub Actions should use
- `GHCR_USERNAME` - your GitHub username
- `GHCR_PAT` - a GitHub personal access token with `read:packages`

## What the workflow does

- runs `python manage.py check` on pull requests and pushes
- on push to `main`, builds a Docker image and pushes it to GHCR
- on the server, logs into GHCR and pulls the new image
- runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

## Server expectations

- Docker is installed
- Docker Compose plugin is installed
- the app lives in `/srv/rentalution`
- the user in `DEPLOY_USER` can run Docker

## Server setup

Create the target directory once:

```bash
sudo mkdir -p /srv/rentalution
sudo chown -R ubuntu:ubuntu /srv/rentalution
```

Then copy your `docker-compose.yml`, `docker-compose.prod.yml`, `.env`, and any persistent files there.
