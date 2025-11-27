import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')

app = Celery('realestate')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# NO automatic cleanup - data retention should be a manual business decision

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')