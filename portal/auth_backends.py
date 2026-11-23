"""Backends AD y local sobre TBL_USUARIO_GC, sin tablas AUTH_* de Django."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from .active_directory import (
    DirectoryDependencyError,
    DirectoryUnavailable,
    authenticate_against_directory,
    direct_corporate_code,
    is_corporate_identifier,
)


class PortalUserBackend(BaseBackend):
    user_fields = (
        "id_usuario",
        "username",
        "nombre_completo",
        "email",
        "puesto",
        "password",
        "rol",
        "is_active",
    )

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            user = user_model.objects.only(*self.user_fields).get(pk=user_id)
        except user_model.DoesNotExist:
            return None
        return user if user.is_active else None

    def has_perm(self, user_obj, perm, obj=None):
        return user_obj.has_perm(perm, obj) if user_obj else False


class ClaroActiveDirectoryBackend(PortalUserBackend):
    @sensitive_variables("password")
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or "").strip()
        if not identifier or password is None or not is_corporate_identifier(identifier):
            return None
        if not settings.LDAP_HABILITADO:
            if request is not None:
                request._portal_auth_status = "directory_unavailable"
            return None

        user_model = get_user_model()
        code = direct_corporate_code(identifier)
        if code is None:
            try:
                mapped = user_model.objects.only("username").get(email__iexact=identifier)
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                return None
            code = direct_corporate_code(mapped.username)
            if code is None:
                return None

        try:
            identity = authenticate_against_directory(code, password)
        except (DirectoryUnavailable, DirectoryDependencyError):
            if request is not None:
                request._portal_auth_status = "directory_unavailable"
            return None
        if identity is None:
            return None

        with transaction.atomic():
            try:
                user = user_model.objects.select_for_update().get(username__iexact=code)
            except user_model.DoesNotExist:
                user = user_model(
                    username=code,
                    nombre_completo=identity.full_name[:150],
                    email=(identity.email or None),
                    puesto=(identity.job_title[:200] or None),
                    rol=user_model.ROLE_USER,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save(force_insert=True)
                return user

            if not user.is_active:
                if request is not None:
                    request._portal_auth_status = "portal_inactive"
                return None

            user.nombre_completo = identity.full_name[:150]
            user.email = identity.email or None
            user.puesto = identity.job_title[:200] or None
            user.set_unusable_password()
            user.save(
                update_fields=(
                    "nombre_completo",
                    "email",
                    "puesto",
                    "password",
                    "fecha_modificacion",
                )
            )
            return user


class RestrictedPortalBackend(PortalUserBackend):
    @sensitive_variables("password")
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        if is_corporate_identifier(username):
            return None
        user_model = get_user_model()
        try:
            user = user_model.objects.only(*self.user_fields).get(
                username__iexact=username.strip()
            )
        except user_model.DoesNotExist:
            make_password(password)
            return None
        if user.check_password(password):
            if user.is_active:
                return user
            if request is not None:
                request._portal_auth_status = "portal_inactive"
        return None


# Compatibilidad con configuraciones antiguas que aún referencien esta clase.
PortalBackend = RestrictedPortalBackend
