"""Servidor WSGI para Windows. No crea tablas ni ejecuta migraciones."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from waitress import serve

from config.wsgi import application


if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8000"))
    threads = int(os.getenv("WEB_THREADS", "8"))
    serve(application, host=host, port=port, threads=threads)
