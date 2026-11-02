from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.database import database_config, oracle_connect_kwargs, read_oracle_password


def oracle_env(**changes):
    values = {
        "DB_ENGINE": "oracle",
        "ORACLE_HOST": "scan-odscbio",
        "ORACLE_PORT": "1521",
        "ORACLE_SERVICE_NAME": "ODSCBIO",
        "ORACLE_USER": "USRFACDOC[USRVALCBIO]",
        "ORACLE_PASSWORD": "test-secret",
        "ORACLE_POOL": "false",
    }
    values.update(changes)
    return values


def test_oracle_defaults_to_direct_connection_without_pool(tmp_path):
    config = database_config(oracle_env(), tmp_path)
    assert config["ENGINE"] == "django.db.backends.oracle"
    assert config["USER"] == "USRFACDOC[USRVALCBIO]"
    assert "(HOST=scan-odscbio)(PORT=1521)" in config["NAME"]
    assert "(SERVICE_NAME=ODSCBIO)" in config["NAME"]
    assert config["OPTIONS"] == {}
    assert config["CONN_MAX_AGE"] == 0


def test_password_file_removes_only_line_endings(tmp_path):
    path = tmp_path / "oracle_password.txt"
    path.write_text("  secret with spaces  \r\n", encoding="utf-8")
    value = read_oracle_password({"ORACLE_PASSWORD_FILE": str(path)}, tmp_path)
    assert value == "  secret with spaces  "


def test_relative_password_path_uses_project_root(tmp_path):
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "oracle_password.txt").write_text("secret\n", encoding="utf-8")
    credentials = oracle_connect_kwargs(
        {"ORACLE_PASSWORD_FILE": "secrets/oracle_password.txt"}, tmp_path
    )
    assert credentials["password"] == "secret"


@pytest.mark.parametrize("user", ["USRFACDOC]", "[USRVALCBIO]", "USRFACDOC[]"])
def test_invalid_proxy_user_is_rejected(tmp_path, user):
    with pytest.raises(ImproperlyConfigured, match="formato proxy válido"):
        database_config(oracle_env(ORACLE_USER=user), tmp_path)


def test_pool_can_only_be_enabled_explicitly(tmp_path):
    config = database_config(oracle_env(ORACLE_POOL="true"), tmp_path)
    assert config["OPTIONS"] == {"pool": {"homogeneous": False}}
