FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Run Django and Celery as an unprivileged account.  Celery refuses to run as
# root by default because a compromised task would otherwise own the container.
RUN groupadd --gid 10001 rentalution \
    && useradd --uid 10001 --gid rentalution --create-home --shell /usr/sbin/nologin rentalution

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg build-essential libjpeg62-turbo-dev libpq-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv
RUN pip install gunicorn celery

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

COPY . /app

RUN mkdir -p /app/media /app/staticfiles \
    && chown -R rentalution:rentalution /app

USER rentalution

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "rentalution.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
