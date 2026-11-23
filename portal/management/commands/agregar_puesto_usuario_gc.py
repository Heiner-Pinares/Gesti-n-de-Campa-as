"""Agrega de forma explícita e idempotente el puesto laboral del usuario."""

import os

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs
from validaciones.management.commands.verificar_oracle import friendly_oracle_error


CONFIRMATION = "AGREGAR_PUESTO_GC"
TABLE_NAME = "TBL_USUARIO_GC"
COLUMN_NAME = "PUESTO"
ADD_COLUMN_SQL = (
    "ALTER TABLE TBL_USUARIO_GC ADD (PUESTO VARCHAR2(200 CHAR))"
)


def column_definition(cursor):
    cursor.execute(
        """
        SELECT DATA_TYPE, CHAR_LENGTH, NULLABLE
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
        """,
        {"table_name": TABLE_NAME, "column_name": COLUMN_NAME},
    )
    return cursor.fetchone()


class Command(BaseCommand):
    help = "Agrega PUESTO a TBL_USUARIO_GC sin modificar los usuarios existentes."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirmacion", default="")

    def handle(self, *args, **options):
        if options["apply"] and options["confirmacion"] != CONFIRMATION:
            raise CommandError(
                f"Confirmación inválida. Use --confirmacion {CONFIRMATION}."
            )

        expected_schema = (os.getenv("ORACLE_SCHEMA") or "USRVALCBIO").strip().upper()
        credentials = oracle_connect_kwargs(os.environ, settings.BASE_DIR)
        connection = None
        try:
            connection = oracledb.connect(**credentials)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL"
                )
                current_schema = cursor.fetchone()[0].upper()
                if current_schema != expected_schema:
                    raise CommandError(
                        f"Esquema actual inesperado: {current_schema}. "
                        f"Se esperaba {expected_schema}."
                    )

                cursor.execute(
                    "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :table_name",
                    {"table_name": TABLE_NAME},
                )
                if cursor.fetchone()[0] != 1:
                    raise CommandError(
                        f"No existe {TABLE_NAME}. Instale primero el esquema GC."
                    )

                existing = column_definition(cursor)
                if existing:
                    data_type, char_length, _ = existing
                    if data_type != "VARCHAR2" or int(char_length or 0) < 200:
                        raise CommandError(
                            f"{TABLE_NAME}.{COLUMN_NAME} existe con una definición "
                            "incompatible; solicite revisión del DBA."
                        )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{TABLE_NAME}.{COLUMN_NAME} ya existe y es compatible."
                        )
                    )
                    return

                self.stdout.write(
                    f"Cambio pendiente: {TABLE_NAME}.{COLUMN_NAME} VARCHAR2(200 CHAR)."
                )
                if not options["apply"]:
                    self.stdout.write(
                        self.style.WARNING("Modo plan: no se ejecutó DDL.")
                    )
                    return

                cursor.execute(ADD_COLUMN_SQL)
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()

        self.stdout.write(
            self.style.SUCCESS(
                f"Columna creada: {TABLE_NAME}.{COLUMN_NAME}. "
                "No se modificaron usuarios existentes."
            )
        )
