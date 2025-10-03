#!/bin/sh
set -e

echo "== ls /app =="; ls -la /app
echo "== ls /app/ANK =="; ls -la /app/ANK

# DB migrations + static
python ANK/manage.py migrate --noinput
python ANK/manage.py collectstatic --noinput

# Start ASGI
exec daphne -b 0.0.0.0 -p 8000 ANK.asgi:application

# #!/usr/bin/env bash
# set -euo pipefail

# echo "== ls /app =="; ls -la /app
# echo "== ls /app/ANK =="; ls -la /app/ANK

# # ---- RELEASE PHASE ----
# python ANK/manage.py migrate --noinput
# python ANK/manage.py ensure_superuser || true
# python ANK/manage.py collectstatic --noinput

# # ---- WEB PHASE ----
# exec daphne -b 0.0.0.0 -p "${PORT:-8000}" ANK.asgi:application
