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
```

Grafana uses the existing `APP_EMAIL_PASSWORD` and Zoho SMTP credentials. Do
not duplicate that password in a monitoring configuration file.

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

- non-2xx Stripe Connect webhook deliveries;
- three or more application critical errors, exceptions, tracebacks, or Celery
  Beat schedule failures within five minutes.
- a required application container that is stopped or restarting.

These dashboard and alert resources are read-only in the Grafana UI because
they are version controlled under `monitoring/grafana/provisioning/`. Change
the files and redeploy to update them.

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
sum(count_over_time({job="nginx-access"} |= "/transaction/stripe/connect/webhook/" |~ " (4|5)[0-9]{2} " [5m]))
```

The Stripe alert fires above zero. This catches a delivery failure such as the
previous Nginx Basic Auth rejection.

```logql
sum(count_over_time({job="docker"} |~ "(?i)(traceback|critical|exception|stripe webhook verification failed)" [5m]))
```

The application alert fires at three events in five minutes to avoid a single
noisy line paging you. Tune exclusions after observing normal traffic.

When Telegram is ready, add a Grafana Telegram contact point using the bot
token and chat ID; keep email as the fallback contact point.
