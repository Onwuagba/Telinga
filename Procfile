release: python manage.py migrate
web: gunicorn telinga.wsgi
worker: celery -A telinga.celery worker -l info
beat: celery -A telinga.celery beat -l info