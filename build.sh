#!/usr/bin/env bash
# Render runs this on every deploy (see render.yaml).
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Demo profile (/u/demo, password demo12345) so there's something to look at.
# seed_demo is safe to re-run: it resets only the demo users.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo
fi

# Optional admin account for moderation (US-11): set DJANGO_SUPERUSER_USERNAME,
# DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD in the Render dashboard.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  python manage.py createsuperuser --no-input || echo "Superuser already exists."
fi
