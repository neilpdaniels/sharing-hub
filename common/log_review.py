"""Deterministic production-log review backed by Loki.

This deliberately does not use an LLM.  A notification about an outage must
be repeatable, auditable and still work if a third-party AI service is down.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings


APPLICATION_QUERY = (
    '{job="docker", service=~"web|worker|video-worker|catalog-ai-worker|beat"} '
    '|~ "(?i)(error|exception|traceback|critical|fatal|panic|out of memory|no space left)"'
)
NGINX_QUERY = '{job="nginx-error"}'

# These are high-confidence operational failures.  Everything else remains in
# the digest as ACTION_REQUIRED for a human to review; it cannot page merely
# because an AI happened to sound confident.
CRITICAL_PATTERN = re.compile(
    r'(?i)(\bcritical\b|\bfatal\b|\bpanic\b|out of memory|no space left|'
    r'database.*(unavailable|corrupt)|could not connect to.*(database|redis)|'
    r'(stripe|payment).*(webhook|signature).*(failed|error))'
)
TIMESTAMP_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}[ T][^ ]+\s+')
UUID_PATTERN = re.compile(r'\b[0-9a-f]{8}-[0-9a-f-]{27,}\b', re.I)
EMAIL_PATTERN = re.compile(r'\b[^\s@]+@[^\s@]+\.[^\s@]+\b')
LONG_NUMBER_PATTERN = re.compile(r'\b\d{4,}\b')
TOKEN_PATTERN = re.compile(r'(?i)((?:token|secret|password|authorization)[=:\s]+)([^\s,;]+)')


@dataclass
class LogEvent:
    timestamp: str
    source: str
    message: str


def _redact(value: str) -> str:
    value = TOKEN_PATTERN.sub(r'\1[REDACTED]', value)
    value = EMAIL_PATTERN.sub('[EMAIL]', value)
    value = UUID_PATTERN.sub('[UUID]', value)
    return value


def normalise_signature(message: str) -> str:
    """Return a stable, privacy-reduced fingerprint for grouping log lines."""
    message = TIMESTAMP_PREFIX.sub('', message.strip())
    message = _redact(message)
    message = LONG_NUMBER_PATTERN.sub('[NUMBER]', message)
    return message[:500]


def load_suppressions(path: str | Path | None = None) -> list[dict[str, str]]:
    path = Path(path or getattr(settings, 'LOG_REVIEW_SUPPRESSIONS_FILE', 'monitoring/log-review-suppressions.json'))
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError('Log-review suppressions must be a JSON list.')
    suppressions = []
    for item in data:
        if not isinstance(item, dict) or not item.get('pattern') or not item.get('reason'):
            raise ValueError('Each log-review suppression needs pattern and reason.')
        re.compile(item['pattern'])
        suppressions.append({'pattern': item['pattern'], 'reason': item['reason']})
    return suppressions


def _matching_suppression(message: str, suppressions: list[dict[str, str]]) -> str | None:
    for suppression in suppressions:
        if re.search(suppression['pattern'], message, flags=re.IGNORECASE):
            return suppression['reason']
    return None


def _loki_events(query: str, start: datetime, end: datetime, loki_url: str) -> list[LogEvent]:
    params = urlencode({
        'query': query,
        'start': str(int(start.timestamp() * 1_000_000_000)),
        'end': str(int(end.timestamp() * 1_000_000_000)),
        'limit': '5000',
        'direction': 'forward',
    })
    with urlopen(f'{loki_url.rstrip("/")}/loki/api/v1/query_range?{params}', timeout=20) as response:  # nosec B310 - controlled internal URL
        payload = json.load(response)
    if payload.get('status') != 'success':
        raise RuntimeError(f'Loki returned an unsuccessful response: {payload!r}')

    events = []
    for stream in payload.get('data', {}).get('result', []):
        labels = stream.get('stream', {})
        source = labels.get('service') or labels.get('job') or 'unknown'
        for timestamp_ns, message in stream.get('values', []):
            timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1_000_000_000, tz=timezone.utc).isoformat()
            events.append(LogEvent(timestamp=timestamp, source=source, message=message))
    return events


def build_report(hours: int = 6, *, now: datetime | None = None, loki_url: str | None = None,
                 suppressions_path: str | Path | None = None) -> dict[str, Any]:
    if hours < 1 or hours > 168:
        raise ValueError('hours must be between 1 and 168.')
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(hours=hours)
    loki_url = loki_url or getattr(settings, 'LOKI_URL', 'http://loki:3100')
    suppressions = load_suppressions(suppressions_path)

    events = _loki_events(APPLICATION_QUERY, start, end, loki_url)
    events.extend(_loki_events(NGINX_QUERY, start, end, loki_url))
    groups: dict[tuple[str, str], list[LogEvent]] = defaultdict(list)
    suppressed: dict[str, int] = defaultdict(int)
    for event in events:
        reason = _matching_suppression(event.message, suppressions)
        if reason:
            suppressed[reason] += 1
            continue
        groups[(event.source, normalise_signature(event.message))].append(event)

    issues = []
    for (source, signature), grouped_events in groups.items():
        severity = 'CRITICAL' if CRITICAL_PATTERN.search(signature) else 'ACTION_REQUIRED'
        issues.append({
            'severity': severity,
            'source': source,
            'count': len(grouped_events),
            'first_seen': grouped_events[0].timestamp,
            'last_seen': grouped_events[-1].timestamp,
            'fingerprint': signature,
        })
    issues.sort(key=lambda issue: (issue['severity'] != 'CRITICAL', -issue['count'], issue['fingerprint']))
    status = 'CRITICAL' if any(issue['severity'] == 'CRITICAL' for issue in issues) else ('ACTION_REQUIRED' if issues else 'OK')
    return {
        'schema_version': 1,
        'status': status,
        'window': {'hours': hours, 'start': start.isoformat(), 'end': end.isoformat()},
        'events_examined': len(events),
        'issues': issues,
        'suppressed': [{'reason': reason, 'count': count} for reason, count in sorted(suppressed.items())],
    }


def report_as_text(report: dict[str, Any]) -> str:
    window = report['window']
    lines = [
        f"Rentalution log review — {report['status']}",
        f"Window: {window['start']} to {window['end']} ({window['hours']} hours)",
        f"Events examined: {report['events_examined']}",
    ]
    if not report['issues']:
        lines.append('No unsuppressed application or Nginx error signatures found.')
    else:
        lines.append('')
        lines.append('Unsuppressed issues:')
        for issue in report['issues']:
            lines.extend((
                f"- [{issue['severity']}] {issue['source']} ×{issue['count']}",
                f"  {issue['fingerprint']}",
                f"  First: {issue['first_seen']}  Last: {issue['last_seen']}",
            ))
    if report['suppressed']:
        lines.append('')
        lines.append('Suppressed by local policy:')
        lines.extend(f"- {item['reason']}: {item['count']} event(s)" for item in report['suppressed'])
    lines.extend(('', 'To adjust false positives, edit monitoring/log-review-suppressions.json, review its reason, then redeploy.'))
    return '\n'.join(lines)


def report_as_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
