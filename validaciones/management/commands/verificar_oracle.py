"""Diagnóstico de conexión Oracle de solo lectura."""

import os

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs


SESSION_SQL = """
SELECT
    SYS_CONTEXT('USERENV', 'SERVICE_NAME') AS SERVICE_NAME,
    SYS_CONTEXT('USERENV', 'SESSION_USER') AS SESSION_USER,
    SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AS CURRENT_SCHEMA,
    SYS_CONTEXT('USERENV', 'PROXY_USER') AS PROXY_USER
FROM DUAL
"""


def friendly_oracle_error(error):
    code = getattr(getattr(error, "args", [None])[0], "code", None)
    messages = {
        1017: "Credenciales Oracle rechazadas.",
        12154: "No se pudo resolver el descriptor Oracle.",
        12514: "El listener no reconoce el servicio configurado.",
        12541: "No se pudo contactar al listener Oracle.",
        28000: "La cuenta Oracle está bloqueada.",
    }
    if code in messages:
        return messages[code]
    if code == 20001:
        return "Oracle rechazó la sesión mediante un control de acceso. Revise el mensaje con el DBA."
    return "No se pudo completar el diagnóstico Oracle. Revise red, servicio, permisos y configuración."


class Command(BaseCommand):
    help = "Comprueba una sesión Oracle sin crear objetos ni modificar datos."

    def handle(self, *args, **options):
        credentials = oracle_connect_kwargs(os.environ, settings.BASE_DIR)
        connection = None
        try:
            connection = oracledb.connect(**credentials)
            with connection.cursor() as cursor:
                cursor.execute(SESSION_SQL)
                service, session_user, current_schema, proxy_user = cursor.fetchone()
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()
        self.stdout.write(
            self.style.SUCCESS(
                "Conexión Oracle de solo lectura comprobada: "
                f"servicio={service}, sesión={session_user}, "
                f"esquema={current_schema}, proxy={proxy_user or 'N/A'}."
            )
        )
