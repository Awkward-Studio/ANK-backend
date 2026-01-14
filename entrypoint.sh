#!/bin/sh
set -e

cd /app/ANK

export DJANGO_SETTINGS_MODULE=ANK.settings

# Migrate + collect static
python manage.py migrate --noinput
python manage.py collectstatic --noinput

python manage.py ensure_superuser || true

# Start ASGI server pointing at the inner package
exec daphne -b 0.0.0.0 -p 8000 ANK.asgi:application