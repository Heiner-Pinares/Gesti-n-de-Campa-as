"""Carga y valida el DDL Oracle autorizado del portal."""

import re
from dataclasses import dataclass
from pathlib import Path

import sqlparse


TABLE_PREFIX = "TBL_"
TABLE_SUFFIX = "_GC"
DDL_FILE = Path(__file__).resolve().parent.parent / "sql" / "oracle" / "001_create_tables_gc.sql"
EXPECTED_TABLES = {
    "TBL_USUARIO_GC",
    "TBL_CAMPANA_VERSION_GC",
    "TBL_VALIDACION_EJECUCION_GC",
    "TBL_VALIDACION_RESULTADO_GC",
    "TBL_AUDITORIA_CAMBIO_GC",
}


@dataclass(frozen=True)
class SchemaObject:
    object_type: str
    name: str
    ddl: str


OBJECT_PATTERN = re.compile(
    r"\bCREATE\s+(?:(UNIQUE)\s+)?(TABLE|INDEX)\s+([A-Z][A-Z0-9_]*)\b",
    re.IGNORECASE,
)


def load_schema_objects(path=DDL_FILE):
    source = Path(path).read_text(encoding="utf-8")
    objects = []
    for statement in sqlparse.split(source):
        ddl = statement.strip().rstrip(";").strip()
        if not ddl:
            continue
        match = OBJECT_PATTERN.search(ddl)
        if not match:
            raise ValueError("El archivo contiene una sentencia DDL no autorizada.")
        object_type = match.group(2).upper()
        name = match.group(3).upper()
        objects.append(SchemaObject(object_type, name, ddl))

    tables = {item.name for item in objects if item.object_type == "TABLE"}
    if tables != EXPECTED_TABLES:
        raise ValueError("El conjunto de tablas del DDL no coincide con el modelo aprobado.")
    if any(not name.startswith(TABLE_PREFIX) or not name.endswith(TABLE_SUFFIX) for name in tables):
        raise ValueError("Todas las tablas deben iniciar con TBL_ y terminar con _GC.")
    return objects
