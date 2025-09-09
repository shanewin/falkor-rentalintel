#!/bin/bash

# Exit on error
set -e

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Start Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn realestate.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info