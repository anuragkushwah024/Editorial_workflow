#!/usr/bin/env bash
# Render build command: bash build.sh
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
# Creates every table, the timeline trigger (0002) and the search index (0003).
python manage.py migrate --no-input

# Render's free plan has no shell, so demo data can be created during the
# build: set SEED_DEMO=True in the Render environment. --skip-if-exists makes
# later deploys skip it instead of failing (the demo can only be created once).
if [ "$SEED_DEMO" = "True" ]; then
  python manage.py seed_demo --skip-if-exists
fi
