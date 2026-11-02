from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("campanas/", views.campanas, name="campanas"),
    path("validaciones/", views.validaciones, name="validaciones"),
]
