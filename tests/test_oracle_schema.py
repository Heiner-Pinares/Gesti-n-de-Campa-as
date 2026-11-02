from portal.oracle_schema import EXPECTED_TABLES, load_schema_objects


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
