from portal.oracle_schema import EXPECTED_TABLES, load_schema_objects
from portal.management.commands.reparar_fechas_gc import existing_column_definition


def test_all_new_tables_follow_required_naming():
    objects = load_schema_objects()
    tables = {item.name for item in objects if item.object_type == "TABLE"}

    assert tables == EXPECTED_TABLES
    assert len(tables) == 5
    assert all(name.startswith("TBL_") and name.endswith("_GC") for name in tables)


def test_schema_contains_only_create_table_and_index():
    objects = load_schema_objects()

    assert objects
    assert {item.object_type for item in objects} <= {"TABLE", "INDEX"}
    for item in objects:
        normalized = " ".join(item.ddl.upper().split())
        assert normalized.startswith(("CREATE TABLE ", "CREATE INDEX ", "CREATE UNIQUE INDEX "))
        assert not any(keyword in normalized for keyword in (" DROP ", " TRUNCATE ", " DELETE ", " UPDATE ", " INSERT ", " MERGE "))


def test_schema_timestamps_are_compatible_with_oracle_thin():
    objects = load_schema_objects()
    table_ddl = "\n".join(item.ddl.upper() for item in objects if item.object_type == "TABLE")

    assert "TIMESTAMP(6) WITH TIME ZONE" not in table_ddl
    assert "DEFAULT SYSTIMESTAMP" not in table_ddl
    assert "TIMESTAMP(6) DEFAULT LOCALTIMESTAMP" in table_ddl


def test_existing_timestamp_repair_does_not_repeat_not_null():
    definition = existing_column_definition("FECHA_CREACION", has_default=True)

    assert definition == "FECHA_CREACION TIMESTAMP(6) DEFAULT LOCALTIMESTAMP"
    assert "NOT NULL" not in definition
