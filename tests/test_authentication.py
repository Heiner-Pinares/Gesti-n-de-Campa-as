from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.apps import apps
from django.contrib.auth import authenticate
from django.db import connection
from django.test import RequestFactory, override_settings
from django.urls import reverse

from portal.active_directory import (
    DirectoryDependencyError,
    DirectoryIdentity,
    DirectoryUnavailable,
    authenticate_against_directory,
    direct_corporate_code,
    is_corporate_identifier,
    validate_ldap_dependencies,
)
from portal.models import PortalUser


IDENTITY = DirectoryIdentity(
    code="C27826",
    given_name="Heiner",
    surname="Pinares",
    email="heiner.pinares@claro.com.pe",
    display_name="Heiner Pinares",
    job_title="Analista de Facturación",
)


def test_login_form_explains_corporate_and_local_identifiers(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Código C/E o usuario local" in html
    assert 'autocomplete="username"' in html
    assert "Ingresa con tu cuenta de dominio" in html


@pytest.fixture
def user_table():
    with connection.schema_editor() as editor:
        editor.create_model(PortalUser)
    yield
    with connection.schema_editor() as editor:
        editor.delete_model(PortalUser)


@pytest.mark.django_db(transaction=True)
def test_valid_corporate_code_creates_minimum_privilege_user(client, user_table):
    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=IDENTITY
    ) as directory:
        response = client.post(
            reverse("login"),
            {"username": "c27826", "password": "solo-en-memoria"},
        )

    assert response.status_code == 302
    directory.assert_called_once_with("C27826", "solo-en-memoria")
    user = PortalUser.objects.get(username="C27826")
    assert user.nombre_completo == "Heiner Pinares"
    assert user.email == "heiner.pinares@claro.com.pe"
    assert user.puesto == "Analista de Facturación"
    assert user.rol == PortalUser.ROLE_ANALYST
    assert user.is_active
    assert not user.has_usable_password()
    assert "solo-en-memoria" not in user.password


@pytest.mark.django_db(transaction=True)
def test_existing_corporate_user_preserves_role_and_syncs_profile(client, user_table):
    user = PortalUser.objects.create_user(
        username="C27826",
        password="clave-local-antigua",
        nombre_completo="Nombre anterior",
        email="anterior@claro.com.pe",
        rol=PortalUser.ROLE_ADMIN,
    )

    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=IDENTITY
    ):
        response = client.post(
            reverse("login"),
            {"username": "C27826", "password": "clave-dominio"},
        )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.rol == PortalUser.ROLE_ADMIN
    assert user.nombre_completo == "Heiner Pinares"
    assert user.email == "heiner.pinares@claro.com.pe"
    assert user.puesto == "Analista de Facturación"
    assert not user.has_usable_password()


@pytest.mark.django_db(transaction=True)
def test_corporate_code_never_falls_back_to_local_password(user_table):
    PortalUser.objects.create_user(
        username="C27826",
        password="clave-local",
        nombre_completo="Usuario corporativo",
        rol=PortalUser.ROLE_ADMIN,
    )

    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=None
    ):
        user = authenticate(username="C27826", password="clave-local")

    assert user is None


@pytest.mark.django_db(transaction=True)
def test_local_non_corporate_user_still_authenticates(user_table):
    expected = PortalUser.objects.create_user(
        username="OPERADOR_LOCAL",
        password="clave-local-segura",
        nombre_completo="Operador local",
        rol=PortalUser.ROLE_ANALYST,
    )

    user = authenticate(username="operador_local", password="clave-local-segura")

    assert user == expected


@pytest.mark.django_db(transaction=True)
def test_direct_corporate_email_uses_directory_backend(client, user_table):
    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=IDENTITY
    ) as directory:
        response = client.post(
            reverse("login"),
            {"username": "C27826@claro.com.pe", "password": "clave-dominio"},
        )

    assert response.status_code == 302
    directory.assert_called_once_with("C27826", "clave-dominio")


@pytest.mark.django_db(transaction=True)
def test_known_nominal_corporate_email_maps_to_corporate_code(client, user_table):
    PortalUser.objects.create_user(
        username="C27826",
        password="clave-local-antigua",
        nombre_completo="Nombre anterior",
        email="heiner.pinares@claro.com.pe",
        rol=PortalUser.ROLE_ANALYST,
    )

    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=IDENTITY
    ) as directory:
        response = client.post(
            reverse("login"),
            {
                "username": "heiner.pinares@claro.com.pe",
                "password": "clave-dominio",
            },
        )

    assert response.status_code == 302
    directory.assert_called_once_with("C27826", "clave-dominio")


@pytest.mark.django_db(transaction=True)
def test_unknown_nominal_corporate_email_never_uses_local_backend(user_table):
    PortalUser.objects.create_user(
        username="heiner.pinares@claro.com.pe",
        password="clave-local",
        nombre_completo="Registro local incorrecto",
        rol=PortalUser.ROLE_ADMIN,
    )

    user = authenticate(
        username="heiner.pinares@claro.com.pe", password="clave-local"
    )

    assert user is None


@pytest.mark.django_db(transaction=True)
def test_inactive_portal_account_shows_controlled_message(client, user_table):
    PortalUser.objects.create_user(
        username="C27826",
        password="clave-local-antigua",
        nombre_completo="Cuenta suspendida",
        rol=PortalUser.ROLE_ANALYST,
        is_active=False,
    )

    with patch(
        "portal.auth_backends.authenticate_against_directory", return_value=IDENTITY
    ):
        response = client.post(
            reverse("login"),
            {"username": "C27826", "password": "clave-dominio"},
        )

    assert response.status_code == 200
    assert "Esta cuenta no tiene el acceso habilitado." in response.content.decode()


@pytest.mark.django_db(transaction=True)
def test_directory_outage_is_controlled_and_never_returns_500(client, user_table):
    with patch(
        "portal.auth_backends.authenticate_against_directory",
        side_effect=DirectoryUnavailable("sin conexión"),
    ):
        response = client.post(
            reverse("login"),
            {"username": "E12345", "password": "clave-dominio"},
        )

    assert response.status_code == 200
    assert (
        "No pudimos validar tu contraseña de dominio en este momento. "
        "Intenta nuevamente en unos minutos."
    ) in response.content.decode()


@pytest.mark.django_db(transaction=True)
def test_local_inactive_account_uses_same_controlled_message(client, user_table):
    PortalUser.objects.create_user(
        username="OPERADOR_LOCAL",
        password="clave-local-segura",
        nombre_completo="Operador suspendido",
        rol=PortalUser.ROLE_ANALYST,
        is_active=False,
    )

    response = client.post(
        reverse("login"),
        {"username": "OPERADOR_LOCAL", "password": "clave-local-segura"},
    )

    assert response.status_code == 200
    assert "Esta cuenta no tiene el acceso habilitado." in response.content.decode()


def test_identifier_classification_is_strict():
    assert is_corporate_identifier("C27826", ("claro.com.pe",))
    assert is_corporate_identifier("e12345", ("claro.com.pe",))
    assert is_corporate_identifier("persona@claro.com.pe", ("claro.com.pe",))
    assert direct_corporate_code("c27826@claro.com.pe") == "C27826"
    assert not is_corporate_identifier("C2782", ("claro.com.pe",))
    assert not is_corporate_identifier("C278260", ("claro.com.pe",))
    assert not is_corporate_identifier("persona@externo.pe", ("claro.com.pe",))


def test_missing_md4_dependency_is_detected_before_production():
    def fake_import(name):
        if name == "ldap3":
            return SimpleNamespace()
        raise ModuleNotFoundError(name)

    with patch("portal.active_directory.import_module", side_effect=fake_import):
        with pytest.raises(DirectoryDependencyError, match="MD4"):
            validate_ldap_dependencies()


@override_settings(
    LDAP_MODO="plano",
    LDAP_HOST="claro.pe",
    LDAP_DOMINIO_NETBIOS="CLARO",
    LDAP_BASE_DN="dc=claro,dc=pe",
    LDAP_TIMEOUT_CONEXION=5,
    LDAP_TIMEOUT_RESPUESTA=10,
    LDAP_CA_CERT="",
)
def test_mocked_ldap_validator_uses_ntlm_search_and_always_unbinds():
    entry = SimpleNamespace(
        entry_attributes_as_dict={
            "givenName": ["Heiner"],
            "sn": ["Pinares"],
            "mail": ["heiner.pinares@claro.com.pe"],
            "displayName": ["Heiner Pinares"],
            "title": ["Analista de Facturación"],
            "userAccountControl": ["512"],
        }
    )
    connection = Mock()
    connection.bind.return_value = True
    connection.search.return_value = True
    connection.entries = [entry]
    fake_ldap = SimpleNamespace(
        Server=Mock(return_value="server"),
        Connection=Mock(return_value=connection),
        NONE="NONE",
        NTLM="NTLM",
        SUBTREE="SUBTREE",
    )
    escape = Mock(return_value="C27826")

    def fake_import(name):
        if name == "ldap3":
            return fake_ldap
        if name == "ldap3.utils.conv":
            return SimpleNamespace(escape_filter_chars=escape)
        raise AssertionError(name)

    with patch("portal.active_directory.validate_ldap_dependencies"), patch(
        "portal.active_directory.import_module", side_effect=fake_import
    ):
        identity = authenticate_against_directory("C27826", "clave-no-persistida")

    assert identity == IDENTITY
    fake_ldap.Connection.assert_called_once_with(
        "server",
        user="CLARO\\C27826",
        password="clave-no-persistida",
        authentication="NTLM",
        receive_timeout=10,
        raise_exceptions=False,
    )
    connection.search.assert_called_once_with(
        search_base="dc=claro,dc=pe",
        search_filter="(sAMAccountName=C27826)",
        search_scope="SUBTREE",
        attributes=(
            "givenName",
            "sn",
            "mail",
            "displayName",
            "title",
            "userAccountControl",
        ),
        size_limit=1,
    )
    connection.unbind.assert_called_once_with()


@override_settings(
    LDAP_MODO="plano",
    LDAP_HOST="claro.pe",
    LDAP_DOMINIO_NETBIOS="CLARO",
    LDAP_BASE_DN="dc=claro,dc=pe",
    LDAP_TIMEOUT_CONEXION=5,
    LDAP_TIMEOUT_RESPUESTA=10,
    LDAP_CA_CERT="",
)
def test_mocked_ldap_validator_rejects_disabled_account():
    entry = SimpleNamespace(
        entry_attributes_as_dict={
            "givenName": ["Cuenta"],
            "sn": ["Deshabilitada"],
            "userAccountControl": ["514"],
        }
    )
    connection = Mock()
    connection.bind.return_value = True
    connection.search.return_value = True
    connection.entries = [entry]
    fake_ldap = SimpleNamespace(
        Server=Mock(return_value="server"),
        Connection=Mock(return_value=connection),
        NONE="NONE",
        NTLM="NTLM",
        SUBTREE="SUBTREE",
    )

    def fake_import(name):
        if name == "ldap3":
            return fake_ldap
        if name == "ldap3.utils.conv":
            return SimpleNamespace(escape_filter_chars=lambda value: value)
        raise AssertionError(name)

    with patch("portal.active_directory.validate_ldap_dependencies"), patch(
        "portal.active_directory.import_module", side_effect=fake_import
    ):
        identity = authenticate_against_directory("E12345", "clave-no-persistida")

    assert identity is None
    connection.unbind.assert_called_once_with()


@pytest.mark.parametrize(
    ("mode", "port", "use_ssl", "starts_tls"),
    (
        ("plano", 389, False, False),
        ("starttls", 389, False, True),
        ("ldaps", 636, True, False),
    ),
)
def test_ldap_transport_modes_are_prepared(
    mode, port, use_ssl, starts_tls, caplog
):
    connection = Mock()
    connection.bind.return_value = False
    connection.result = {"result": 49, "message": "data 52e"}
    connection.start_tls.return_value = True
    fake_ldap = SimpleNamespace(
        Server=Mock(return_value="server"),
        Connection=Mock(return_value=connection),
        NONE="NONE",
        NTLM="NTLM",
        SUBTREE="SUBTREE",
    )

    def fake_import(name):
        if name == "ldap3":
            return fake_ldap
        if name == "ldap3.utils.conv":
            return SimpleNamespace(escape_filter_chars=lambda value: value)
        raise AssertionError(name)

    with override_settings(
        LDAP_MODO=mode,
        LDAP_HOST="claro.pe",
        LDAP_DOMINIO_NETBIOS="CLARO",
        LDAP_BASE_DN="dc=claro,dc=pe",
        LDAP_TIMEOUT_CONEXION=5,
        LDAP_TIMEOUT_RESPUESTA=10,
        LDAP_CA_CERT="",
    ), patch("portal.active_directory.validate_ldap_dependencies"), patch(
        "portal.active_directory._tls_configuration", return_value="tls"
    ), patch("portal.active_directory.import_module", side_effect=fake_import):
        assert authenticate_against_directory("C27826", "clave-no-persistida") is None

    fake_ldap.Server.assert_called_once_with(
        "claro.pe",
        port=port,
        use_ssl=use_ssl,
        tls="tls" if mode != "plano" else None,
        connect_timeout=5,
        get_info="NONE",
    )
    if starts_tls:
        connection.open.assert_called_once_with()
        connection.start_tls.assert_called_once_with()
    else:
        connection.open.assert_not_called()
        connection.start_tls.assert_not_called()
    connection.unbind.assert_called_once_with()
    assert "clave-no-persistida" not in caplog.text


def test_authentication_adds_no_models_or_tables():
    portal_tables = {
        model._meta.db_table
        for model in apps.get_app_config("portal").get_models()
    }
    assert portal_tables == {
        "TBL_USUARIO_GC",
        "TBL_CAMPANA_VERSION_GC",
        "TBL_VALIDACION_EJECUCION_GC",
        "TBL_VALIDACION_RESULTADO_GC",
        "TBL_AUDITORIA_CAMBIO_GC",
    }


@pytest.mark.django_db(transaction=True)
def test_backend_marks_dependency_failure_as_directory_outage(user_table):
    request = RequestFactory().post(reverse("login"))
    with patch(
        "portal.auth_backends.authenticate_against_directory",
        side_effect=DirectoryDependencyError("sin MD4"),
    ):
        user = authenticate(
            request=request, username="C27826", password="clave-dominio"
        )

    assert user is None
    assert request._portal_auth_status == "directory_unavailable"
