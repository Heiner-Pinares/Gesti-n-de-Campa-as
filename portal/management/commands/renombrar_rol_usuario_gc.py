"""Renombra de forma explícita el rol básico ANALISTA a USUARIO."""

import os

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs
from validaciones.management.commands.verificar_oracle import friendly_oracle_error


CONFIRMATION = "RENOMBRAR_ROL_USUARIO_GC"
TABLE_NAME = "TBL_USUARIO_GC"
CONSTRAINT_NAME = "CK_USU_ROL_GC"
ALLOWED_ROLES = {"ADMINISTRADOR", "ANALISTA", "USUARIO"}
DROP_CONSTRAINT_SQL = (
    "ALTER TABLE TBL_USUARIO_GC DROP CONSTRAINT CK_USU_ROL_GC"
)
UPDATE_ROLE_SQL = (
    "UPDATE TBL_USUARIO_GC SET ROL = 'USUARIO', "
    "FECHA_MODIFICACION = LOCALTIMESTAMP WHERE ROL = 'ANALISTA'"
)
DEFAULT_ROLE_SQL = (
    "ALTER TABLE TBL_USUARIO_GC MODIFY (ROL DEFAULT 'USUARIO')"
)
ADD_CONSTRAINT_SQL = (
    "ALTER TABLE TBL_USUARIO_GC ADD CONSTRAINT CK_USU_ROL_GC "
    "CHECK (ROL IN ('ADMINISTRADOR', 'USUARIO'))"
)


def role_counts(cursor):
    cursor.execute(
        "SELECT ROL, COUNT(*) FROM TBL_USUARIO_GC GROUP BY ROL ORDER BY ROL"
    )
    return {str(role): int(count) for role, count in cursor.fetchall()}


def constraint_condition(cursor):
    cursor.execute(
        """
        SELECT SEARCH_CONDITION
        FROM USER_CONSTRAINTS
        WHERE TABLE_NAME = :table_name
          AND CONSTRAINT_NAME = :constraint_name
          AND CONSTRAINT_TYPE = 'C'
        """,
        {"table_name": TABLE_NAME, "constraint_name": CONSTRAINT_NAME},
    )
    row = cursor.fetchone()
    return str(row[0]).upper() if row and row[0] else ""


def role_default(cursor):
    cursor.execute(
        """
        SELECT DATA_DEFAULT
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = :table_name AND COLUMN_NAME = 'ROL'
        """,
        {"table_name": TABLE_NAME},
    )
    row = cursor.fetchone()
    return str(row[0]).upper() if row and row[0] else ""


def schema_is_current(counts, condition, default):
    return (
        not counts.get("ANALISTA", 0)
        and set(counts) <= {"ADMINISTRADOR", "USUARIO"}
        and "'USUARIO'" in condition
        and "'ANALISTA'" not in condition
        and "'USUARIO'" in default
    )


class Command(BaseCommand):
    help = "Cambia el rol básico ANALISTA a USUARIO sin alterar sus permisos."

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
        updated = 0
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

                counts = role_counts(cursor)
                unknown_roles = set(counts) - ALLOWED_ROLES
                if unknown_roles:
                    raise CommandError(
                        "Existen roles no reconocidos: "
                        + ", ".join(sorted(unknown_roles))
                        + ". Solicite revisión antes de continuar."
                    )
                condition = constraint_condition(cursor)
                default = role_default(cursor)
                if schema_is_current(counts, condition, default):
                    self.stdout.write(
                        self.style.SUCCESS(
                            "El rol básico ya es USUARIO y el esquema es compatible."
                        )
                    )
                    return

                self.stdout.write(
                    "Cambio pendiente: ANALISTA -> USUARIO. "
                    f"Registros a actualizar: {counts.get('ANALISTA', 0)}."
                )
                if not options["apply"]:
                    self.stdout.write(
                        self.style.WARNING("Modo plan: no se modificó el esquema.")
                    )
                    return

                if condition:
                    cursor.execute(DROP_CONSTRAINT_SQL)
                cursor.execute(UPDATE_ROLE_SQL)
                updated = cursor.rowcount
                connection.commit()
                cursor.execute(DEFAULT_ROLE_SQL)
                cursor.execute(ADD_CONSTRAINT_SQL)
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()

        self.stdout.write(
            self.style.SUCCESS(
                f"Rol básico actualizado a USUARIO. Registros modificados: {updated}."
            )
        )
