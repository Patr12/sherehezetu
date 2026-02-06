# sherehezetu/celery.py

import os
from celery import Celery

# hii ni settings module ya Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sherehezetu.settings')

app = Celery('sherehezetu')

# read settings from Django, prefix CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# auto discover tasks.py in apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
