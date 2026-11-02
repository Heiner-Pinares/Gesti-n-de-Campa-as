"""Configuración Oracle y lectura segura de credenciales."""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def flag(env, name, default="false"):
    return (env.get(name) or default).strip().lower() == "true"


def _proxy_user(value):
    uses_proxy = "[" in value or "]" in value
    valid = (
        value.count("[") == 1
        and value.count("]") == 1
        and value.index("[") > 0
        and value.endswith("]")
        and value.index("[") < len(value) - 2
    ) if uses_proxy else True
    if not valid:
        raise ImproperlyConfigured(
            "ORACLE_USER no tiene un formato proxy válido; se espera "
            "USUARIO_PROXY[USUARIO_SESION]."
        )
    return uses_proxy


def read_oracle_password(env, base_dir):
    value = env.get("ORACLE_PASSWORD") or ""
    if value:
        return value
    configured = env.get("ORACLE_PASSWORD_FILE") or "secrets/oracle_password.txt"
    path = Path(configured)
    if not path.is_absolute():
        path = Path(base_dir) / path
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except FileNotFoundError as error:
        raise ImproperlyConfigured(
            f"Falta el archivo de contraseña Oracle configurado en {path}."
        ) from error
    except OSError as error:
        raise ImproperlyConfigured(
            f"No se pudo leer el archivo de contraseña Oracle configurado en {path}."
        ) from error
    if not value:
        raise ImproperlyConfigured("La contraseña Oracle configurada está vacía.")
    return value


def oracle_dsn(env):
    configured = (env.get("ORACLE_DSN") or "").strip()
    if configured:
        return configured
    host = (env.get("ORACLE_HOST") or "scan-odscbio").strip()
    port = (env.get("ORACLE_PORT") or "1521").strip()
    service = (env.get("ORACLE_SERVICE_NAME") or "ODSCBIO").strip()
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ImproperlyConfigured("ORACLE_PORT debe ser un puerto válido.")
    if not host or not service:
        raise ImproperlyConfigured("ORACLE_HOST y ORACLE_SERVICE_NAME son obligatorios.")
    return (
        "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
        f"(HOST={host})(PORT={port}))"
        "(CONNECT_DATA=(SERVER=DEDICATED)"
        f"(SERVICE_NAME={service})))"
    )


def oracle_connect_kwargs(env, base_dir):
    user = (env.get("ORACLE_USER") or "USRFACDOC[USRVALCBIO]").strip()
    _proxy_user(user)
    return {
        "user": user,
        "password": read_oracle_password(env, base_dir),
        "dsn": oracle_dsn(env),
    }


def database_config(env, base_dir):
    engine = (env.get("DB_ENGINE") or "oracle").strip().lower()
    if engine in {"sqlite", "sqlite3"}:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env.get("DB_NAME", ":memory:"),
        }
    if engine != "oracle":
        raise ImproperlyConfigured(f"DB_ENGINE no soportado: {engine}")

    credentials = oracle_connect_kwargs(env, base_dir)
    uses_proxy = _proxy_user(credentials["user"])
    options = {}
    if flag(env, "ORACLE_POOL", "false"):
        options["pool"] = {"homogeneous": False} if uses_proxy else True
    return {
        "ENGINE": "django.db.backends.oracle",
        "NAME": credentials["dsn"],
        "USER": credentials["user"],
        "PASSWORD": credentials["password"],
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }
