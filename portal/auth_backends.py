"""Autenticación contra TBL_USUARIO_GC sin depender de tablas AUTH_* de Django."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password


class PortalBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username__iexact=username.strip())
        except user_model.DoesNotExist:
            make_password(password)
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
        return user if user.is_active else None

    def has_perm(self, user_obj, perm, obj=None):
        return user_obj.has_perm(perm, obj) if user_obj else False
