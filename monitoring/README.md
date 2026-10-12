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
default data source.

Open `http://localhost:3001`, create the Uptime Kuma administrator account,
then add an HTTP(s) monitor for:

```text
https://rentalution.co.uk/healthz/
```

In Uptime Kuma, add the existing Zoho SMTP account as an email notification
provider and route monitor failures to `MONITORING_ALERT_EMAIL`.

## Recommended Grafana alerts

Create Grafana-managed Loki alerts for these queries:

```logql
sum(count_over_time({job="nginx-access"} |= "/transaction/stripe/connect/webhook/" |~ " (4|5)[0-9]{2} " [5m]))
```

Alert when the result is greater than zero. This catches a Stripe delivery
failure such as the previous Nginx Basic Auth rejection.

```logql
sum(count_over_time({job="docker"} |~ "(?i)(traceback|critical|exception|stripe webhook verification failed)" [5m]))
```

Start with a threshold above zero and tune exclusions after observing normal
application traffic.

When Telegram is ready, add a Grafana Telegram contact point using the bot
token and chat ID; keep email as the fallback contact point.
