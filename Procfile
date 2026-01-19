web: sh -c "gunicorn realestate.wsgi:application --bind 0.0.0.0:$PORT"
release: python manage.py migrate
worker: celery -A realestate worker -l info
beat: celery -A realestate beat -l info