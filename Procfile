web: ./start.sh
release: python manage.py migrate
worker: celery -A realestate worker -l info
beat: celery -A realestate beat -l info