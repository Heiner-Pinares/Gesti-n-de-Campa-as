from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("campanas/", views.campanas, name="campanas"),
    path("campanas/nueva/", views.campaign_create, name="campaign_create"),
    path("campanas/fuente-comercial/", views.commercial_source, name="commercial_source"),
    path(
        "campanas/fuente-comercial/descargar/",
        views.commercial_source_download,
        name="commercial_source_download",
    ),
    path("campanas/<str:record_key>/", views.campaign_edit, name="campaign_edit"),
    path("validaciones/", views.validaciones, name="validaciones"),
    path("validaciones/ejecutar/", views.validation_start, name="validation_start"),
    path("validaciones/resultados/<int:result_id>/", views.validation_detail, name="validation_detail"),
    path("validaciones/ejecuciones/<int:execution_id>/exportar/", views.validation_export, name="validation_export"),
]
