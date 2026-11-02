"""Convierte fechas TSTZ del esquema inicial a TIMESTAMP compatible con Thin."""

import os

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs
from validaciones.management.commands.verificar_oracle import friendly_oracle_error


CONFIRMATION = "REPARAR_FECHAS_GC"
TIMESTAMP_COLUMNS = {
    "TBL_USUARIO_GC": {
        "ULTIMO_ACCESO": (True, False),
        "FECHA_CREACION": (False, True),
        "FECHA_MODIFICACION": (False, True),
    },
    "TBL_CAMPANA_VERSION_GC": {
        "FECHA_CREACION": (False, True),
        "FECHA_MODIFICACION": (False, True),
    },
    "TBL_VALIDACION_EJECUCION_GC": {
        "FECHA_SOLICITUD": (False, True),
        "FECHA_INICIO": (True, False),
        "FECHA_FIN": (True, False),
    },
    "TBL_VALIDACION_RESULTADO_GC": {
        "FECHA_REGISTRO": (False, True),
    },
    "TBL_AUDITORIA_CAMBIO_GC": {
        "FECHA_EVENTO": (False, True),
    },
}
BUSINESS_TABLES = set(TIMESTAMP_COLUMNS) - {"TBL_USUARIO_GC"}


def column_definition(column, nullable, has_default):
    definition = f"{column} TIMESTAMP(6)"
    if has_default:
        definition += " DEFAULT LOCALTIMESTAMP"
    if not nullable:
        definition += " NOT NULL"
    return definition


def column_type(cursor, table, column):
    cursor.execute(
        """
        SELECT DATA_TYPE
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
        """,
        {"table_name": table, "column_name": column},
    )
    row = cursor.fetchone()
    return row[0] if row else None


def row_count(cursor, table):
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


class Command(BaseCommand):
    help = "Repara las fechas del esquema GC creado con zona horaria no compatible con Thin."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirmacion", default="")

    def handle(self, *args, **options):
        if options["apply"] and options["confirmacion"] != CONFIRMATION:
            raise CommandError(f"Confirmación inválida. Use --confirmacion {CONFIRMATION}.")

        expected_schema = (os.getenv("ORACLE_SCHEMA") or "USRVALCBIO").strip().upper()
        credentials = oracle_connect_kwargs(os.environ, settings.BASE_DIR)
        connection = None
        changed = []
        try:
            connection = oracledb.connect(**credentials)
            with connection.cursor() as cursor:
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
                current_schema = cursor.fetchone()[0].upper()
                if current_schema != expected_schema:
                    raise CommandError(
                        f"Esquema actual inesperado: {current_schema}. Se esperaba {expected_schema}."
                    )

                pending = []
                for table, columns in TIMESTAMP_COLUMNS.items():
                    for column in columns:
                        data_type = column_type(cursor, table, column)
                        if data_type and "WITH TIME ZONE" in data_type:
                            pending.append((table, column, data_type))
                if not pending:
                    self.stdout.write(self.style.SUCCESS("Las fechas GC ya son compatibles con Oracle Thin."))
                    return

                self.stdout.write("Columnas que requieren reparación:")
                for table, column, data_type in pending:
                    self.stdout.write(f"- {table}.{column}: {data_type} -> TIMESTAMP(6)")
                if not options["apply"]:
                    self.stdout.write(self.style.WARNING("Modo plan: no se modificaron columnas."))
                    return

                for table in BUSINESS_TABLES:
                    if row_count(cursor, table) != 0:
                        raise CommandError(
                            f"{table} ya contiene datos. Se detuvo la reparación para revisión manual."
                        )

                for table, columns in TIMESTAMP_COLUMNS.items():
                    table_rows = row_count(cursor, table)
                    for column, (nullable, has_default) in columns.items():
                        data_type = column_type(cursor, table, column)
                        temporary = f"{column}_FIX"
                        temporary_type = column_type(cursor, table, temporary)

                        if data_type and "WITH TIME ZONE" not in data_type:
                            continue
                        if table_rows == 0 and data_type:
                            cursor.execute(
                                f"ALTER TABLE {table} MODIFY "
                                f"({column_definition(column, nullable, has_default)})"
                            )
                            changed.append(f"{table}.{column}")
                            continue

                        if not data_type and temporary_type:
                            cursor.execute(
                                f"ALTER TABLE {table} RENAME COLUMN {temporary} TO {column}"
                            )
                        elif data_type:
                            if not temporary_type:
                                cursor.execute(
                                    f"ALTER TABLE {table} ADD ({temporary} TIMESTAMP(6))"
                                )
                            cursor.execute(
                                f"UPDATE {table} SET {temporary} = SYS_EXTRACT_UTC({column}) "
                                f"WHERE {column} IS NOT NULL"
                            )
                            connection.commit()
                            cursor.execute(
                                f"SELECT COUNT(*) FROM {table} "
                                f"WHERE {column} IS NOT NULL AND {temporary} IS NULL"
                            )
                            if cursor.fetchone()[0]:
                                raise CommandError(
                                    f"No se pudo preservar completamente {table}.{column}."
                                )
                            cursor.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
                            cursor.execute(
                                f"ALTER TABLE {table} RENAME COLUMN {temporary} TO {column}"
                            )
                        else:
                            raise CommandError(f"No se encontró {table}.{column}.")

                        cursor.execute(
                            f"ALTER TABLE {table} MODIFY "
                            f"({column_definition(column, nullable, has_default)})"
                        )
                        changed.append(f"{table}.{column}")

                remaining = []
                for table, columns in TIMESTAMP_COLUMNS.items():
                    for column in columns:
                        data_type = column_type(cursor, table, column)
                        if data_type and "WITH TIME ZONE" in data_type:
                            remaining.append(f"{table}.{column}")
                if remaining:
                    raise CommandError("Persisten columnas incompatibles: " + ", ".join(remaining))
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()

        self.stdout.write(self.style.SUCCESS(f"Columnas reparadas: {len(changed)}."))
        for name in changed:
            self.stdout.write(f"- {name}")
