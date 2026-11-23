"""Comprobaciones no destructivas para publicar el portal en Windows."""

from __future__ import annotations

import socket
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class ProductionCheck:
    level: str
    name: str
    detail: str


def _result(level, name, detail):
    return ProductionCheck(level=level, name=name, detail=detail)


def _check_write_access(directory, name):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix="portal-check-", delete=True):
            pass
    except OSError:
        return _result("ERROR", name, f"No se puede escribir en {directory}.")
    return _result("OK", name, f"Escritura comprobada en {directory}.")


def _check_port(port):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("0.0.0.0", port))
    except OSError:
        return _result(
            "ERROR",
            "puerto",
            f"El puerto {port} está ocupado o no puede reservarse en 0.0.0.0.",
        )
    finally:
        listener.close()
    return _result("OK", "puerto", f"El puerto {port} está disponible.")


def run_production_checks(port, *, skip_port_check=False):
    """Ejecuta controles; nunca autentica a un usuario contra Active Directory."""
    checks = []

    try:
        from run import runtime_options

        bind_address, configured_port, _ = runtime_options()
        if configured_port != port:
            checks.append(
                _result(
                    "ERROR",
                    "escucha",
                    f"El puerto efectivo ({configured_port}) no coincide con el solicitado ({port}).",
                )
            )
        else:
            checks.append(
                _result(
                    "OK",
                    "escucha",
                    f"Waitress escuchará en {bind_address}:{configured_port}.",
                )
            )
    except (TypeError, ValueError) as error:
        checks.append(_result("ERROR", "escucha", str(error)))

    if sys.version_info[:2] == (3, 12):
        checks.append(_result("OK", "python", "Python 3.12 detectado."))
    else:
        checks.append(
            _result(
                "ADVERTENCIA",
                "python",
                f"Se recomienda Python 3.12; versión activa: {sys.version.split()[0]}.",
            )
        )

    if settings.DEBUG:
        checks.append(_result("ERROR", "django", "DEBUG debe permanecer en False."))
    else:
        checks.append(_result("OK", "django", "DEBUG=False."))

    if not settings.ALLOWED_HOSTS:
        checks.append(_result("ERROR", "hosts", "ALLOWED_HOSTS está vacío."))
    elif "*" in settings.ALLOWED_HOSTS:
        checks.append(
            _result(
                "ADVERTENCIA",
                "hosts",
                "ALLOWED_HOSTS=* sirve para la prueba interna, pero debe limitarse al nombre o IP definitivos.",
            )
        )
    else:
        checks.append(_result("OK", "hosts", "ALLOWED_HOSTS está limitado."))
        if not {"127.0.0.1", "localhost"}.intersection(settings.ALLOWED_HOSTS):
            checks.append(
                _result(
                    "ERROR",
                    "hosts",
                    "ALLOWED_HOSTS debe incluir 127.0.0.1 o localhost para la comprobación local del proceso.",
                )
            )

    if settings.AUTO_MIGRATE:
        checks.append(_result("ERROR", "migraciones", "AUTO_MIGRATE debe ser false."))
    elif settings.MIGRATION_MODULES.get("portal") is not None or settings.MIGRATION_MODULES.get("validaciones") is not None:
        checks.append(_result("ERROR", "migraciones", "Las migraciones administradas deben continuar deshabilitadas."))
    else:
        checks.append(_result("OK", "migraciones", "No se ejecutarán migraciones automáticas."))

    database_engine = settings.DATABASES["default"]["ENGINE"]
    if not database_engine.endswith("oracle"):
        checks.append(_result("ERROR", "oracle", "Producción debe usar DB_ENGINE=oracle."))
    else:
        try:
            from run import comprobar_base_datos

            comprobar_base_datos()
        except Exception:
            checks.append(
                _result(
                    "ERROR",
                    "oracle",
                    "Falló la conexión real, la sesión proxy o la comprobación del esquema TBL_*_GC.",
                )
            )
        else:
            checks.append(_result("OK", "oracle", "Conexión y esquema Oracle comprobados."))

    static_root = Path(settings.STATIC_ROOT).resolve()
    static_sources = {Path(item).resolve() for item in settings.STATICFILES_DIRS}
    if static_root in static_sources:
        checks.append(
            _result(
                "ERROR",
                "estáticos",
                "STATIC_ROOT debe ser una carpeta de salida exclusiva, distinta de STATICFILES_DIRS.",
            )
        )
    else:
        checks.append(_result("OK", "estáticos", "STATIC_ROOT es una salida exclusiva."))
        checks.append(_check_write_access(static_root, "estáticos"))

    checks.append(_check_write_access(Path(settings.BASE_DIR) / "logs" / "portal", "logs"))
    checks.append(_check_write_access(Path(settings.BASE_DIR) / "runtime-config" / "portal", "runtime"))

    if settings.LDAP_HABILITADO:
        try:
            from portal.active_directory import validate_ldap_dependencies

            validate_ldap_dependencies()
        except Exception:
            checks.append(_result("ERROR", "ldap", "Falta ldap3 o el proveedor MD4 de pycryptodome."))
        else:
            checks.append(_result("OK", "ldap", "Dependencias LDAP/NTLM disponibles."))

        ldap_port = 636 if settings.LDAP_MODO == "ldaps" else 389
        try:
            connection = socket.create_connection(
                (settings.LDAP_HOST, ldap_port),
                timeout=settings.LDAP_TIMEOUT_CONEXION,
            )
            connection.close()
        except OSError:
            checks.append(
                _result(
                    "ERROR",
                    "ldap",
                    f"No hay conectividad TCP con {settings.LDAP_HOST}:{ldap_port}.",
                )
            )
        else:
            checks.append(
                _result(
                    "OK",
                    "ldap",
                    f"Conectividad TCP con {settings.LDAP_HOST}:{ldap_port}; no se realizó autenticación.",
                )
            )

        if settings.LDAP_MODO == "plano":
            checks.append(
                _result(
                    "ADVERTENCIA",
                    "ldap",
                    "LDAP usa el modo plano por compatibilidad; solicite LDAPS o StartTLS a TI.",
                )
            )
    else:
        checks.append(_result("ADVERTENCIA", "ldap", "LDAP_HABILITADO=false."))

    if settings.SESSION_COOKIE_SECURE:
        checks.append(_result("OK", "https", "Las cookies seguras están habilitadas."))
    else:
        checks.append(
            _result(
                "ADVERTENCIA",
                "https",
                "COOKIE_SECURE=false: aceptable solo para una publicación HTTP interna aprobada.",
            )
        )

    checks.append(
        _result(
            "ADVERTENCIA",
            "correo",
            "El portal no tiene integración de correo; no hay servidor SMTP que validar.",
        )
    )

    if not skip_port_check:
        checks.append(_check_port(port))
    return checks
