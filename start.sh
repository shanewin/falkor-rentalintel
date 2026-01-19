#!/bin/bash

# Ensure we have a port
PORT=${PORT:-8000}

echo "Starting Gunicorn on port $PORT..."
exec gunicorn realestate.wsgi:application --bind 0.0.0.0:$PORT