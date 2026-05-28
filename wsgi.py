"""Точка входа WSGI для Gunicorn / uWSGI (в т.ч. Docker)."""
from app import create_app

app = create_app()
