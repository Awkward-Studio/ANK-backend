#!/usr/bin/env bash
set -euo pipefail

# Fail fast if critical envs missing (so you see clear errors)
: "${SECRET_KEY:?SECRET_KEY not set}"
: "${DATABASE_URL:?DATABASE_URL not set}"
: "${REDIS_URL:?REDIS_URL not set}"

# ---- RELEASE PHASE ----
# python 3.11.4; run in container startup so every deploy migrates, creates superuser, collects static
python manage.py migrate --noinput
python manage.py ensure_superuser || true
python manage.py collectstatic --noinput

# ---- WEB PHASE ----
PORT="${PORT:-8000}"
exec daphne -b 0.0.0.0 -p "$PORT" ANK.asgi:application
