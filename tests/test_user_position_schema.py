from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from portal.management.commands.agregar_puesto_usuario_gc import ADD_COLUMN_SQL


class FakeCursor:
    def __init__(self, existing_column=None):
        self.existing_column = existing_column
        self.row = None
        self.executed_ddl = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, parameters=None):
        normalized = " ".join(statement.upper().split())
        if "CURRENT_SCHEMA" in normalized:
            self.row = ("USRVALCBIO",)
        elif "FROM USER_TABLES" in normalized:
            self.row = (1,)
        elif "FROM USER_TAB_COLUMNS" in normalized:
            self.row = self.existing_column
        elif normalized.startswith("ALTER TABLE"):
            self.executed_ddl.append(" ".join(statement.split()))
            self.row = None
        else:
            raise AssertionError(f"SQL inesperado: {normalized}")

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, existing_column=None):
        self.fake_cursor = FakeCursor(existing_column)
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


def test_position_upgrade_adds_only_the_nullable_column(monkeypatch):
    monkeypatch.setenv("ORACLE_SCHEMA", "USRVALCBIO")
    connection = FakeConnection()
    output = StringIO()

    with patch(
        "portal.management.commands.agregar_puesto_usuario_gc.oracle_connect_kwargs",
        return_value={},
    ), patch(
        "portal.management.commands.agregar_puesto_usuario_gc.oracledb.connect",
        return_value=connection,
    ):
        call_command(
            "agregar_puesto_usuario_gc",
            apply=True,
            confirmacion="AGREGAR_PUESTO_GC",
            stdout=output,
        )

    assert connection.fake_cursor.executed_ddl == [ADD_COLUMN_SQL]
    assert connection.closed
    assert "No se modificaron usuarios existentes" in output.getvalue()


def test_position_upgrade_is_idempotent(monkeypatch):
    monkeypatch.setenv("ORACLE_SCHEMA", "USRVALCBIO")
    connection = FakeConnection(existing_column=("VARCHAR2", 200, "Y"))
    output = StringIO()

    with patch(
        "portal.management.commands.agregar_puesto_usuario_gc.oracle_connect_kwargs",
        return_value={},
    ), patch(
        "portal.management.commands.agregar_puesto_usuario_gc.oracledb.connect",
        return_value=connection,
    ):
        call_command(
            "agregar_puesto_usuario_gc",
            apply=True,
            confirmacion="AGREGAR_PUESTO_GC",
            stdout=output,
        )

    assert connection.fake_cursor.executed_ddl == []
    assert connection.closed
    assert "ya existe y es compatible" in output.getvalue()
