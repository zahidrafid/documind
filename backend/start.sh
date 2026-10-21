#!/usr/bin/env bash
set -euo pipefail

# Apply any new migrations (Render's free plan has no separate pre-deploy step)
python manage.py migrate --noinput

# Background worker: one process, minimal Redis traffic to fit the free tier
celery -A config worker --loglevel=info --pool=solo \
  --without-gossip --without-mingle --without-heartbeat &

# Web server
gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 &

# If either process stops, exit so Render restarts the container
wait -n
exit $?
