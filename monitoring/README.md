# Production monitoring

The production Compose stack runs these services on loopback-only ports:

- Grafana: `127.0.0.1:3000`
- Uptime Kuma: `127.0.0.1:3001`
- Loki: internal only
- Grafana Alloy: internal only; reads Docker and Nginx logs and sends them to Loki

## Required production `.env` values

```dotenv
MONITORING_ALERT_EMAIL=neil_p_Daniels@hotmail.com
GRAFANA_ADMIN_PASSWORD=<unique password>
GRAFANA_SECRET_KEY=<long random value>
# Private Tailscale Serve URL, used by links in Grafana alert emails.
GRAFANA_ROOT_URL=https://vps-name.your-tailnet.ts.net
```

Grafana uses the existing `APP_EMAIL_PASSWORD` and Zoho SMTP credentials. Do
not duplicate that password in a monitoring configuration file.

After enabling Tailscale Serve for Grafana, set `GRAFANA_ROOT_URL` to its
HTTPS URL and recreate Grafana. Alert emails will then link to the private
Grafana dashboard/alert pages rather than `localhost:3000`.

## First-use setup

Tunnel the private monitoring ports from a trusted computer:

```bash
./scripts/open_monitoring_tunnel.sh
```

The wrapper defaults to `ubuntu@rentalution`; pass another SSH destination as
its first argument when required.

Open `http://localhost:3000` and sign in as `admin` with
`GRAFANA_ADMIN_PASSWORD`. Grafana automatically has Loki configured as its
default data source, the **Rentalution / Rentalution operations** dashboard,
and these configuration-backed email alerts:

- Stripe Connect webhook 5xx responses;
- high-confidence application failures: explicit critical/fatal/panic entries,
  out-of-memory or disk exhaustion, unavailable/corrupt database or Redis, and
  Stripe/payment webhook or signature failures.
- a required application container that is stopped or restarting.

These dashboard and alert resources are read-only in the Grafana UI because
they are version controlled under `monitoring/grafana/provisioning/`. Change
the files and redeploy to update them.

Alert e-mails show the triggering alert, service, evaluated event count, and a
direct link to the relevant dashboard panel. They are grouped by alert name,
sent no more often than every 15 minutes while a condition persists, repeated
after 12 hours, and do not send a separate resolved e-mail. Grafana alert
templates cannot query Loki for raw log lines, so the e-mail deliberately links
to the **Recent errors** panel rather than claiming to contain a top-ten log
extract.

## Deterministic log-review digest

Grafana is the immediate, minute-by-minute escalation path. Separately, the
Celery Beat job can send a grouped review digest every six hours. It queries
Loki for Docker application errors and Nginx errors, removes secrets and
personal identifiers from the e-mail fingerprints, groups repeats, and labels
only high-confidence infrastructure or payment failures as `CRITICAL`. Other
unrecognised error groups are `ACTION_REQUIRED` for a person to investigate.
No AI is used to decide whether an alert is critical.

First test it manually on the VPS (this prints JSON only and sends nothing):

```bash
cd /srv/rentalution
docker compose -f docker-compose.prod.yml exec -T web \
  python manage.py review_production_logs --hours 6 --json
```

Then test e-mail delivery:

```bash
docker compose -f docker-compose.prod.yml exec -T web \
  python manage.py review_production_logs --hours 6 --email
```

Once the output and recipient are right, add these to the production `.env`
and redeploy:

```dotenv
LOG_REVIEW_SCHEDULED_ENABLED=1
LOG_REVIEW_HOURS=6
# Optional; defaults to MONITORING_ALERT_EMAIL.
LOG_REVIEW_RECIPIENTS=neil_p_daniels@rentalution.co.uk
```

To suppress a confirmed benign fingerprint, add a narrowly-scoped regular
expression and a human reason to `monitoring/log-review-suppressions.json`,
then redeploy. Keep rules specific and review them periodically; a suppression
must never be used to hide a real outage.

## Discord notifications

Grafana's Discord contact point requires a channel webhook URL, not merely the
Discord server. In Discord, open the target channel's **Edit Channel** →
**Integrations** → **Webhooks**, create a webhook, and copy its URL. Treat that
URL as a secret: it permits posting to that channel. Set it as
`DISCORD_WEBHOOK_URL` in the deployment environment; the provisioned
`Rentalution alerts` contact point sends general alerts to Discord as well as
e-mail. Set `DISCORD_ERROR_LOG_WEBHOOK_URL` to a different, restricted Discord
channel; it receives the application error excerpts. Rotate a webhook
immediately if it is exposed.

Discord includes at most ten of the most frequent matching application-error
lines per alert evaluation, with each excerpt capped at 500 characters. Those
excerpts are intentionally Discord-only; e-mail retains the compact summary.
Keep the Discord channel restricted, because application logs can contain
operationally sensitive data.

To test the application-error route after deployment, emit three identical
synthetic critical lines through the web container's normal stdout stream:

```bash
cd /srv/rentalution
docker compose -f docker-compose.prod.yml exec -T web sh -c '
  for n in 1 2 3; do
    printf "%s\n" "CRITICAL rentalution-discord-alert-test Exception: synthetic monitoring test" > /proc/1/fd/1
  done
'
```

The lines appear in the **Recent errors** panel. The alert evaluates every
minute, must remain present for one minute, and has a one-minute notification
group wait, so allow up to three minutes for the restricted error-log Discord
channel to receive it.

`container-watchdog` inspects Docker state for `web`, the Celery workers,
Beat, PostgreSQL, and Redis. Access to Docker's Unix socket is privileged even
when mounted read-only, so do not expose this service or mount that socket into
unrelated containers.

Open `http://localhost:3001`, create the Uptime Kuma administrator account,
then add an HTTP(s) monitor for:

```text
https://rentalution.co.uk/healthz/
```

In Uptime Kuma, add the existing Zoho SMTP account as an email notification
provider and route monitor failures to `MONITORING_ALERT_EMAIL`.

## Alert queries

The provisioned rules use these LogQL queries:

```logql
sum(count_over_time({job="nginx-access"} |= "/transaction/stripe/connect/webhook/" |~ " 5[0-9]{2} " [5m]))
```

The Stripe alert fires above zero. A webhook 4xx is retained in Nginx access
logs for investigation, but it does not page Discord; this avoids waking you
for malformed or unauthorised requests while retaining urgent 5xx failures.

```logql
sum(count_over_time({job="docker"} |~ "(?i)(\\bcritical\\b|\\bfatal\\b|\\bpanic\\b|out of memory|no space left|database.*(unavailable|corrupt)|could not connect to.*(database|redis)|(stripe|payment).*(webhook|signature).*(failed|error))" [5m]))
```

The application alert fires for one high-confidence critical failure. Ordinary
errors, exceptions and tracebacks are collected in the deterministic review
digest instead of paging Discord.

When Telegram is ready, add a Grafana Telegram contact point using the bot
token and chat ID; keep email as the fallback contact point.
