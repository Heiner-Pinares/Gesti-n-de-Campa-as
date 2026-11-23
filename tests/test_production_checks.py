import socket
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings

import run
from portal.production_checks import _check_port, run_production_checks


def test_port_check_reports_occupied_port_without_terminating_processes(monkeypatch):
    class OccupiedPortProbe:
        closed = False

        def setsockopt(self, *args):
            pass

        def bind(self, address):
            raise OSError("puerto ocupado")

        def close(self):
            self.closed = True

    probe = OccupiedPortProbe()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: probe)

    result = _check_port(8006)

    assert result.level == "ERROR"
    assert probe.closed is True


def test_production_checks_accept_a_valid_non_destructive_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PORTAL_PORT", "8006")
    monkeypatch.setenv("WEB_BIND_ADDRESS", "0.0.0.0")
    monkeypatch.setattr(run, "comprobar_base_datos", lambda: None)
    monkeypatch.setattr(
        settings, "DATABASES", {"default": {"ENGINE": "django.db.backends.oracle"}}
    )
    static_source = tmp_path / "static-source"
    static_source.mkdir()

    with override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["*"],
        AUTO_MIGRATE=False,
        MIGRATION_MODULES={"portal": None, "validaciones": None},
        BASE_DIR=tmp_path,
        STATIC_ROOT=tmp_path / "static-output",
        STATICFILES_DIRS=[static_source],
        LDAP_HABILITADO=False,
        SESSION_COOKIE_SECURE=False,
    ):
        checks = run_production_checks(8006, skip_port_check=True)

    assert not [item for item in checks if item.level == "ERROR"]
    assert any(item.name == "oracle" and item.level == "OK" for item in checks)
    assert any(item.name == "estáticos" and item.level == "OK" for item in checks)


def test_production_checks_reject_a_port_different_from_effective_env(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PORTAL_PORT", "8006")
    monkeypatch.setenv("WEB_BIND_ADDRESS", "0.0.0.0")
    monkeypatch.setattr(run, "comprobar_base_datos", lambda: None)
    monkeypatch.setattr(
        settings, "DATABASES", {"default": {"ENGINE": "django.db.backends.oracle"}}
    )
    source = tmp_path / "source"
    source.mkdir()
    with override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=["*"],
        AUTO_MIGRATE=False,
        MIGRATION_MODULES={"portal": None, "validaciones": None},
        BASE_DIR=tmp_path,
        STATIC_ROOT=tmp_path / "output",
        STATICFILES_DIRS=[source],
        LDAP_HABILITADO=False,
        SESSION_COOKIE_SECURE=False,
    ):
        checks = run_production_checks(9000, skip_port_check=True)

    assert any(item.name == "escucha" and item.level == "ERROR" for item in checks)


@pytest.mark.parametrize(
    "script_name",
    ["portal.ps1", "portal_common.ps1", "validar_portal_windows.ps1", "publicar_portal_windows.ps1"],
)
def test_windows_scripts_do_not_hardcode_the_server_port(script_name):
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts" / script_name).read_text(encoding="utf-8")
    assert "8006" not in content


def test_windows_manager_exposes_required_commands_and_safe_stop_contract():
    root = Path(__file__).resolve().parents[1]
    manager = (root / "scripts" / "portal.ps1").read_text(encoding="utf-8")
    common = (root / "scripts" / "portal_common.ps1").read_text(encoding="utf-8")
    launcher = (root / "scripts" / "portal.cmd").read_text(encoding="utf-8")

    for command in ("start", "stop", "restart", "status", "logs", "validate"):
        assert f'"{command}"' in manager
    assert "Get-CimInstance Win32_Process" in common
    assert "ExecutablePath" in common
    assert "CommandLine" in common
    assert "Stop-Process -Name" not in manager
    assert "taskkill" not in manager.lower()
    assert "Invoke-WebRequest" in manager
    assert '"$($config.LocalUrl)/login/"' in manager
    assert "%~dp0portal.ps1" in launcher


def test_publisher_uses_secure_prompt_and_never_changes_firewall():
    root = Path(__file__).resolve().parents[1]
    publisher = (root / "scripts" / "publicar_portal_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "Read-Host" in publisher and "-AsSecureString" in publisher
    assert "New-ScheduledTaskTrigger -AtStartup" in publisher
    assert "ZeroFreeBSTR" in publisher
    assert "netsh" not in publisher.lower()
    assert "New-NetFirewallRule" not in publisher
