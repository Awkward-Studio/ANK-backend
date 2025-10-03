#!/bin/sh
set -e

echo "== ls /app =="; ls -la /app
echo "== ls /app/ANK =="; ls -la /app/ANK

# DB migrations + static
python ANK/manage.py migrate --noinput
python ANK/manage.py collectstatic --noinput

# Start ASGI
exec daphne -b 0.0.0.0 -p 8000 ANK.ANK.asgi:application

