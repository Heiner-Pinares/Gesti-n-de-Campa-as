from django.contrib.auth import views as auth_views
from django.urls import include, path

from portal.forms import PortalAuthenticationForm

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=PortalAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("portal.urls")),
]
