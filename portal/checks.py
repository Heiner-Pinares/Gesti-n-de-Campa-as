"""Comprobaciones de despliegue para Active Directory."""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

from .active_directory import DirectoryDependencyError, validate_ldap_dependencies


@register(Tags.security)
def active_directory_configuration_check(app_configs, **kwargs):
    if not settings.LDAP_HABILITADO:
        return []

    messages = []
    if settings.LDAP_MODO not in {"plano", "starttls", "ldaps"}:
        messages.append(
            Error(
                "LDAP_MODO debe ser plano, starttls o ldaps.",
                id="portal.E001",
            )
        )
    if not settings.LDAP_HOST or not settings.LDAP_BASE_DN:
        messages.append(
            Error(
                "LDAP_HOST y LDAP_BASE_DN son obligatorios.",
                id="portal.E002",
            )
        )
    if not settings.DOMINIOS_CORREO_CLARO:
        messages.append(
            Error(
                "DOMINIOS_CORREO_CLARO debe contener al menos un dominio.",
                id="portal.E006",
            )
        )
    if settings.LDAP_TIMEOUT_CONEXION <= 0 or settings.LDAP_TIMEOUT_RESPUESTA <= 0:
        messages.append(
            Error(
                "Los tiempos máximos LDAP deben ser mayores que cero.",
                id="portal.E003",
            )
        )
    if settings.LDAP_CA_CERT and not Path(settings.LDAP_CA_CERT).is_file():
        messages.append(
            Error(
                "LDAP_CA_CERT no apunta a un certificado accesible.",
                id="portal.E004",
            )
        )
    try:
        validate_ldap_dependencies()
    except DirectoryDependencyError as error:
        messages.append(Error(str(error), id="portal.E005"))
    if not settings.DEBUG and settings.LDAP_MODO == "plano":
        messages.append(
            Warning(
                "LDAP usa el modo plano por compatibilidad. Solicite a TI habilitar "
                "LDAPS o StartTLS.",
                id="portal.W001",
            )
        )
    return messages
