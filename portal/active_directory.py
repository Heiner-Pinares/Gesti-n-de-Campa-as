"""Cliente Active Directory aislado de la autenticación y del modelo de usuarios."""

from __future__ import annotations

import logging
import re
import ssl
from dataclasses import dataclass
from importlib import import_module

from django.conf import settings
from django.utils.encoding import force_str


logger = logging.getLogger(__name__)

CORPORATE_CODE_RE = re.compile(r"^[CE]\d{5}$", re.IGNORECASE)
AD_ACCOUNT_DISABLED = 0x0002
AD_REJECTION_CODES = {
    "525": "usuario_no_encontrado",
    "52e": "credenciales_invalidas",
    "530": "inicio_restringido_por_hora",
    "531": "inicio_restringido_por_equipo",
    "532": "contrasena_vencida",
    "533": "cuenta_deshabilitada",
    "701": "cuenta_vencida",
    "773": "cambio_de_contrasena_requerido",
    "775": "cuenta_bloqueada",
}


class DirectoryUnavailable(RuntimeError):
    """Active Directory no pudo atender la validación."""


class DirectoryDependencyError(RuntimeError):
    """Falta una dependencia necesaria para LDAP/NTLM."""


@dataclass(frozen=True)
class DirectoryIdentity:
    code: str
    given_name: str = ""
    surname: str = ""
    email: str = ""
    display_name: str = ""

    @property
    def full_name(self):
        return self.display_name or " ".join(
            part for part in (self.given_name, self.surname) if part
        ) or self.code


def validate_ldap_dependencies():
    """Comprueba ldap3 y el proveedor MD4 exigido por NTLM."""
    try:
        import_module("ldap3")
    except (ImportError, ModuleNotFoundError) as error:
        raise DirectoryDependencyError(
            "Falta ldap3. Instale las dependencias bloqueadas del proyecto."
        ) from error

    try:
        md4 = import_module("Crypto.Hash.MD4")
        md4.new(b"comprobacion-ntlm").digest()
    except (ImportError, ModuleNotFoundError, AttributeError, ValueError) as error:
        raise DirectoryDependencyError(
            "Falta el proveedor MD4 de pycryptodome requerido por LDAP/NTLM. "
            "Instale las dependencias bloqueadas del proyecto."
        ) from error


def corporate_email_domain(identifier, domains=None):
    value = (identifier or "").strip()
    if "@" not in value:
        return None
    _, domain = value.rsplit("@", 1)
    allowed = domains if domains is not None else settings.DOMINIOS_CORREO_CLARO
    normalized = {item.strip().casefold() for item in allowed if item.strip()}
    domain = domain.casefold()
    return domain if domain in normalized else None


def is_corporate_identifier(identifier, domains=None):
    value = (identifier or "").strip()
    return bool(CORPORATE_CODE_RE.fullmatch(value)) or bool(
        corporate_email_domain(value, domains)
    )


def direct_corporate_code(identifier):
    value = (identifier or "").strip()
    candidate = value.rsplit("@", 1)[0] if "@" in value else value
    return candidate.upper() if CORPORATE_CODE_RE.fullmatch(candidate) else None


def _first(attributes, name):
    value = attributes.get(name)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return force_str(value or "").strip()


def _rejection_category(result):
    diagnostic = " ".join(
        force_str((result or {}).get(key, "")) for key in ("message", "description")
    ).casefold()
    for code, category in AD_REJECTION_CODES.items():
        if re.search(rf"(?:data\s+|\b){re.escape(code)}\b", diagnostic):
            return category
    return "rechazo_de_credenciales"


def _tls_configuration(ca_cert):
    ldap3 = import_module("ldap3")
    return ldap3.Tls(
        validate=ssl.CERT_REQUIRED,
        ca_certs_file=str(ca_cert) if ca_cert else None,
    )


def authenticate_against_directory(code, password):
    """Valida NTLM, consulta el perfil y devuelve una identidad saneada."""
    connection = None

    try:
        validate_ldap_dependencies()
        ldap3 = import_module("ldap3")
        escape_filter_chars = import_module("ldap3.utils.conv").escape_filter_chars
        mode = settings.LDAP_MODO
        if mode not in {"plano", "starttls", "ldaps"}:
            raise DirectoryUnavailable("El modo LDAP no es válido.")
        port = 636 if mode == "ldaps" else 389
        tls = _tls_configuration(settings.LDAP_CA_CERT) if mode != "plano" else None

        server = ldap3.Server(
            settings.LDAP_HOST,
            port=port,
            use_ssl=mode == "ldaps",
            tls=tls,
            connect_timeout=settings.LDAP_TIMEOUT_CONEXION,
            get_info=ldap3.NONE,
        )
        connection = ldap3.Connection(
            server,
            user=f"{settings.LDAP_DOMINIO_NETBIOS}\\{code}",
            password=password,
            authentication=ldap3.NTLM,
            receive_timeout=settings.LDAP_TIMEOUT_RESPUESTA,
            raise_exceptions=False,
        )

        if mode == "starttls":
            connection.open()
            if not connection.start_tls():
                raise DirectoryUnavailable("No se pudo iniciar el canal StartTLS.")

        if not connection.bind():
            result = connection.result or {}
            logger.info(
                "Autenticación AD rechazada para %s: categoria=%s resultado=%s",
                code,
                _rejection_category(result),
                result.get("result", "sin_codigo"),
            )
            return None

        found = connection.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=f"(sAMAccountName={escape_filter_chars(code)})",
            search_scope=ldap3.SUBTREE,
            attributes=(
                "givenName",
                "sn",
                "mail",
                "displayName",
                "userAccountControl",
            ),
            size_limit=1,
        )
        if not found or not connection.entries:
            logger.warning("Cuenta autenticada sin perfil AD localizable: %s", code)
            return None

        attributes = connection.entries[0].entry_attributes_as_dict
        try:
            user_account_control = int(_first(attributes, "userAccountControl") or 0)
        except (TypeError, ValueError):
            user_account_control = 0
        if user_account_control & AD_ACCOUNT_DISABLED:
            logger.info(
                "Autenticación AD rechazada para %s: categoria=cuenta_deshabilitada",
                code,
            )
            return None

        return DirectoryIdentity(
            code=code,
            given_name=_first(attributes, "givenName"),
            surname=_first(attributes, "sn"),
            email=_first(attributes, "mail"),
            display_name=_first(attributes, "displayName"),
        )
    except (DirectoryUnavailable, DirectoryDependencyError):
        raise
    except Exception as error:
        logger.warning(
            "Active Directory no disponible durante la autenticación de %s: %s",
            code,
            error.__class__.__name__,
        )
        raise DirectoryUnavailable("Active Directory no está disponible.") from error
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                logger.debug("No se pudo cerrar limpiamente la conexión LDAP.")
