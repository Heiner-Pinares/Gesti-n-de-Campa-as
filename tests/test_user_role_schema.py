from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from portal.management.commands.renombrar_rol_usuario_gc import (
    ADD_CONSTRAINT_SQL,
    DEFAULT_ROLE_SQL,
    DROP_CONSTRAINT_SQL,
    UPDATE_ROLE_SQL,
)


class FakeCursor:
    def __init__(self, counts, condition, default):
        self.counts = counts
        self.condition = condition
        self.default = default
        self.row = None
        self.rows = []
        self.rowcount = 0
        self.mutations = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, parameters=None):
        normalized = " ".join(statement.upper().split())
        self.rowcount = 0
        if "CURRENT_SCHEMA" in normalized:
            self.row = ("USRVALCBIO",)
        elif "FROM USER_TABLES" in normalized:
            self.row = (1,)
        elif normalized.startswith("SELECT ROL, COUNT(*)"):
            self.rows = sorted(self.counts.items())
        elif "FROM USER_CONSTRAINTS" in normalized:
            self.row = (self.condition,) if self.condition else None
        elif "FROM USER_TAB_COLUMNS" in normalized:
            self.row = (self.default,) if self.default else None
        elif normalized.startswith(("ALTER TABLE", "UPDATE ")):
            self.mutations.append(" ".join(statement.split()))
            if normalized.startswith("UPDATE "):
                self.rowcount = self.counts.get("ANALISTA", 0)
        else:
            raise AssertionError(f"SQL inesperado: {normalized}")

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, counts, condition, default):
        self.fake_cursor = FakeCursor(counts, condition, default)
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def run_command(connection, output):
    with patch(
        "portal.management.commands.renombrar_rol_usuario_gc.oracle_connect_kwargs",
        return_value={},
    ), patch(
        "portal.management.commands.renombrar_rol_usuario_gc.oracledb.connect",
        return_value=connection,
    ):
        call_command(
            "renombrar_rol_usuario_gc",
            apply=True,
            confirmacion="RENOMBRAR_ROL_USUARIO_GC",
            stdout=output,
        )


def test_role_upgrade_renames_existing_users_and_constraint(monkeypatch):
    monkeypatch.setenv("ORACLE_SCHEMA", "USRVALCBIO")
    connection = FakeConnection(
        counts={"ADMINISTRADOR": 1, "ANALISTA": 8},
        condition="ROL IN ('ADMINISTRADOR', 'ANALISTA')",
        default="'ANALISTA'",
    )
    output = StringIO()

    run_command(connection, output)

    assert connection.fake_cursor.mutations == [
        DROP_CONSTRAINT_SQL,
        UPDATE_ROLE_SQL,
        DEFAULT_ROLE_SQL,
        ADD_CONSTRAINT_SQL,
    ]
    assert connection.commits == 1
    assert connection.closed
    assert "Registros modificados: 8" in output.getvalue()


def test_role_upgrade_is_idempotent(monkeypatch):
    monkeypatch.setenv("ORACLE_SCHEMA", "USRVALCBIO")
    connection = FakeConnection(
        counts={"ADMINISTRADOR": 1, "USUARIO": 8},
        condition="ROL IN ('ADMINISTRADOR', 'USUARIO')",
        default="'USUARIO'",
    )
    output = StringIO()

    run_command(connection, output)

    assert connection.fake_cursor.mutations == []
    assert connection.commits == 0
    assert connection.closed
    assert "ya es USUARIO" in output.getvalue()
