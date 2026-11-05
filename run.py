"""Arranque de producción para el servidor Windows dentro de la red corporativa."""

from __future__ import annotations

import os
import socket
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def obtener_ip_local():
    """Detecta una IPv4 de red sin convertir la detección en requisito de arranque."""
    detected = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # connect() en UDP selecciona la interfaz de salida; no envía información.
        sock.connect(("8.8.8.8", 80))
        detected = sock.getsockname()[0]
    except OSError:
        pass
    finally:
        sock.close()

    if detected and not detected.startswith("127."):
        return detected

    try:
        addresses = socket.getaddrinfo(
            socket.gethostname(), None, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        for address in addresses:
            candidate = address[4][0]
            if candidate and not candidate.startswith("127."):
                return candidate
    except OSError:
        pass
    return None


def runtime_options(environment=None):
    environment = os.environ if environment is None else environment
    host = (environment.get("HOST") or environment.get("WEB_HOST") or "0.0.0.0").strip()
    port = int(environment.get("PORT") or environment.get("WEB_PORT") or "8000")
    threads = int(environment.get("THREADS") or environment.get("WEB_THREADS") or "8")
    if host in LOOPBACK_HOSTS or host != "0.0.0.0":
        raise ValueError("HOST debe ser 0.0.0.0 para permitir el acceso desde la red corporativa.")
    if not 1 <= port <= 65535:
        raise ValueError("PORT debe estar entre 1 y 65535.")
    if threads < 1:
        raise ValueError("THREADS debe ser mayor que cero.")
    return host, port, threads


def comprobar_base_datos():
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection

    if connection.vendor == "oracle":
        call_command("verificar_oracle", verbosity=0)
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        if cursor.fetchone() is None:
            raise RuntimeError("La base de datos no respondió a la consulta de control.")


def preparar_archivos_estaticos():
    from django.core.management import call_command

    call_command("collectstatic", interactive=False, verbosity=0)


def main():
    load_dotenv(BASE_DIR / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        host, port, threads = runtime_options()
    except (TypeError, ValueError) as error:
        print(f"ERROR DE CONFIGURACIÓN: {error}", flush=True)
        return 1

    import django

    django.setup()
    from django.conf import settings

    if settings.DEBUG:
        print("ERROR DE CONFIGURACIÓN: DEBUG debe permanecer en False.", flush=True)
        return 1
    if not settings.ALLOWED_HOSTS:
        print("ERROR DE CONFIGURACIÓN: ALLOWED_HOSTS no puede estar vacío.", flush=True)
        return 1

    print("Comprobando conexión a la base de datos...", flush=True)
    try:
        comprobar_base_datos()
    except Exception:
        print(
            "ERROR: no se pudo comprobar la base de datos. Revise red, servicio, permisos y configuración.",
            flush=True,
        )
        return 1

    print("Preparando archivos estáticos...", flush=True)
    try:
        preparar_archivos_estaticos()
    except Exception:
        print("ERROR: no se pudieron preparar los archivos estáticos.", flush=True)
        return 1

    from config.wsgi import application
    from waitress import serve

    local_ip = obtener_ip_local()
    network_host = local_ip or "IP_DEL_SERVIDOR"
    print("", flush=True)
    print("Portal iniciado.", flush=True)
    print(f"Escuchando en: http://{host}:{port}", flush=True)
    print(f"Acceso local: http://127.0.0.1:{port}", flush=True)
    print(f"Acceso desde la red: http://{network_host}:{port}", flush=True)
    if not local_ip:
        print("No se detectó una IPv4 automáticamente; consulte ipconfig.", flush=True)
    print("Migraciones automáticas: deshabilitadas.", flush=True)
    serve(application, host=host, port=port, threads=threads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
