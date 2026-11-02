"""Inventario de metadatos Oracle en modo estrictamente de solo lectura."""

import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import oracledb
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.database import oracle_connect_kwargs
from .verificar_oracle import friendly_oracle_error


OBJECT_NAMES = (
    "CFG_CAMPANAS_PORTABILIDAD",
    "BASE_CF_BASICO_X",
    "BASE_CF_DESCUENTO_X",
    "CONTRACT_HISTORY",
    "REASONSTATUS_ALL",
    "BASE_FINAL_CAMPANA_HIST",
    "TFUN001_GET_DNNUM_FROM_COID",
)

METADATA_QUERIES = {
    "objetos": """
        SELECT OWNER, OBJECT_NAME, OBJECT_TYPE, STATUS
        FROM ALL_OBJECTS
        WHERE OBJECT_NAME IN ({binds})
        ORDER BY OBJECT_NAME, OWNER, OBJECT_TYPE
    """,
    "sinonimos": """
        SELECT OWNER, SYNONYM_NAME, TABLE_OWNER, TABLE_NAME, DB_LINK
        FROM ALL_SYNONYMS
        WHERE SYNONYM_NAME IN ({binds})
        ORDER BY SYNONYM_NAME, OWNER
    """,
    "columnas": """
        SELECT OWNER, TABLE_NAME, COLUMN_ID, COLUMN_NAME, DATA_TYPE,
               DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE
        FROM ALL_TAB_COLUMNS
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, OWNER, COLUMN_ID
    """,
    "restricciones": """
        SELECT OWNER, TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE,
               STATUS, VALIDATED, R_OWNER, R_CONSTRAINT_NAME
        FROM ALL_CONSTRAINTS
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, OWNER, CONSTRAINT_NAME
    """,
    "columnas_restricciones": """
        SELECT OWNER, TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, POSITION
        FROM ALL_CONS_COLUMNS
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, OWNER, CONSTRAINT_NAME, POSITION
    """,
    "indices": """
        SELECT OWNER, TABLE_OWNER, TABLE_NAME, INDEX_NAME, UNIQUENESS, STATUS
        FROM ALL_INDEXES
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, TABLE_OWNER, INDEX_NAME
    """,
    "columnas_indices": """
        SELECT INDEX_OWNER, TABLE_OWNER, TABLE_NAME, INDEX_NAME,
               COLUMN_NAME, COLUMN_POSITION
        FROM ALL_IND_COLUMNS
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, TABLE_OWNER, INDEX_NAME, COLUMN_POSITION
    """,
    "privilegios": """
        SELECT GRANTEE, TABLE_SCHEMA AS OWNER, TABLE_NAME,
               GRANTOR, PRIVILEGE, GRANTABLE
        FROM ALL_TAB_PRIVS
        WHERE TABLE_NAME IN ({binds})
        ORDER BY TABLE_NAME, OWNER, GRANTEE, PRIVILEGE
    """,
}

CAMPAIGN_COUNT_SQL = """
    SELECT COUNT(*) AS TOTAL_REGISTROS
    FROM USRVALCBIO.CFG_CAMPANAS_PORTABILIDAD
"""


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _fetch_dicts(cursor):
    columns = [item[0].lower() for item in cursor.description]
    return [
        {column: _json_value(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


class Command(BaseCommand):
    help = "Inspecciona metadatos de los objetos del proceso sin modificar Oracle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help="Ruta opcional para guardar el informe JSON sin datos de clientes.",
        )

    def handle(self, *args, **options):
        credentials = oracle_connect_kwargs(os.environ, settings.BASE_DIR)
        report = {
            "modo": "solo_lectura",
            "objetos_solicitados": list(OBJECT_NAMES),
        }
        binds = ", ".join(f":name_{index}" for index in range(len(OBJECT_NAMES)))
        parameters = {
            f"name_{index}": name for index, name in enumerate(OBJECT_NAMES)
        }
        connection = None
        try:
            connection = oracledb.connect(**credentials)
            with connection.cursor() as cursor:
                for section, template in METADATA_QUERIES.items():
                    cursor.execute(template.format(binds=binds), parameters)
                    report[section] = _fetch_dicts(cursor)
                cursor.execute(CAMPAIGN_COUNT_SQL)
                report["conteo_cfg_campanas"] = _fetch_dicts(cursor)[0]
        except oracledb.Error as error:
            raise CommandError(friendly_oracle_error(error)) from error
        finally:
            if connection is not None:
                connection.close()

        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        output = options.get("output")
        if output:
            path = Path(output)
            if not path.is_absolute():
                path = settings.BASE_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered + "\n", encoding="utf-8")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Inspección de solo lectura completada. Informe: {path}"
                )
            )
        else:
            self.stdout.write(rendered)
            self.stdout.write(self.style.SUCCESS("Inspección de solo lectura completada."))
