"""
재생E AI Agent — Celery Configuration
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

app = Celery('re_ai_agent', broker=redis_url, backend=redis_url)
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
