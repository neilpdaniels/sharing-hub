# Hetzner Docker Deployment

## Recommended setup

- Hetzner Cloud VPS in Germany or Finland
- Docker + Docker Compose
- SQLite for first deployment, with persistent bind mounts
- A reverse proxy in front later if you want HTTPS on the same host

## Files added

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `rentalution/settings/production.py`

## First-time server setup

1. Create an Ubuntu VPS on Hetzner.
2. Install Docker and Docker Compose plugin.
3. Clone this repository onto the server.
4. Copy `.env.example` to `.env` and edit it.
5. Make sure your domain DNS points at the server.
6. Run:

```bash
docker compose up -d --build
```

## What to check

- Django starts on port `8000`
- `migrate` runs successfully
- `collectstatic` writes into `staticfiles/`
- uploads persist in `media/`
- the SQLite file persists as `db.sqlite3`

## Next step for a proper public site

Add a reverse proxy such as Caddy or Nginx so you can serve HTTPS on `80/443` and keep Gunicorn private on the Docker network.
