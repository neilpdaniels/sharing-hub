FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libjpeg62-turbo-dev libpq-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv
RUN pip install gunicorn

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

COPY . /app

RUN mkdir -p /app/media /app/staticfiles

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "rentalution.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
