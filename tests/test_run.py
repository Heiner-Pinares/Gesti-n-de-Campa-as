import socket

import pytest

import run


def test_runtime_options_use_corporate_network_defaults():
    assert run.runtime_options({}) == ("0.0.0.0", 8000, 8)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "172.19.194.219"])
def test_runtime_options_reject_non_wildcard_listeners(host):
    with pytest.raises(ValueError, match="HOST debe ser 0.0.0.0"):
        run.runtime_options({"HOST": host})


def test_runtime_options_preserve_legacy_environment_names():
    assert run.runtime_options(
        {"WEB_HOST": "0.0.0.0", "WEB_PORT": "9000", "WEB_THREADS": "4"}
    ) == ("0.0.0.0", 9000, 4)


def test_local_ip_falls_back_to_hostname_addresses(monkeypatch):
    class UnavailableSocket:
        def connect(self, address):
            raise OSError("sin ruta")

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: UnavailableSocket())
    monkeypatch.setattr(socket, "gethostname", lambda: "servidor-corporativo")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.19.194.219", 0)),
        ],
    )

    assert run.obtener_ip_local() == "172.19.194.219"


def test_position_column_is_required_before_startup():
    class MissingColumnCursor:
        def execute(self, statement):
            assert "TBL_USUARIO_GC" in statement
            assert "PUESTO" in statement

        def fetchone(self):
            return (0,)

    with pytest.raises(run.PortalSchemaError, match="add_user_position_gc.ps1"):
        run.comprobar_columna_puesto(MissingColumnCursor())


def test_position_column_allows_startup():
    class CompatibleCursor:
        def execute(self, statement):
            pass

        def fetchone(self):
            return (1,)

    run.comprobar_columna_puesto(CompatibleCursor())


def test_legacy_analyst_role_is_rejected_before_startup():
    class LegacyRoleCursor:
        def execute(self, statement):
            self.statement = statement

        def fetchone(self):
            if "DATA_DEFAULT" in self.statement:
                return ("'ANALISTA'",)
            if "SEARCH_CONDITION" in self.statement:
                return ("ROL IN ('ADMINISTRADOR', 'ANALISTA')",)
            return (2,)

    with pytest.raises(run.PortalSchemaError, match="update_user_schema_gc.ps1"):
        run.comprobar_rol_usuario(LegacyRoleCursor())


def test_user_role_allows_startup():
    class CurrentRoleCursor:
        def execute(self, statement):
            self.statement = statement

        def fetchone(self):
            if "DATA_DEFAULT" in self.statement:
                return ("'USUARIO'",)
            if "SEARCH_CONDITION" in self.statement:
                return ("ROL IN ('ADMINISTRADOR', 'USUARIO')",)
            return (0,)

    run.comprobar_rol_usuario(CurrentRoleCursor())
