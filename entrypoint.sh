#!/usr/bin/env bash
set -euo pipefail

cd /app

# ---- RELEASE PHASE ----
python ANK/manage.py migrate --noinput
python ANK/manage.py ensure_superuser || true
python ANK/manage.py collectstatic --noinput

# ---- WEB PHASE ----
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" ANK.asgi:application
