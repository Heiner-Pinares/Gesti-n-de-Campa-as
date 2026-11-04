from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from openpyxl import Workbook

from portal.models import (
    CampaignVersion,
    ChangeAudit,
    PortalUser,
    ValidationExecution,
    ValidationStoredResult,
)


PORTAL_MODELS = (
    PortalUser,
    CampaignVersion,
    ValidationExecution,
    ValidationStoredResult,
    ChangeAudit,
)


@pytest.fixture
def portal_tables():
    with connection.schema_editor() as editor:
        for model in PORTAL_MODELS:
            editor.create_model(model)
    yield
    with connection.schema_editor() as editor:
        for model in reversed(PORTAL_MODELS):
            editor.delete_model(model)


@pytest.mark.django_db(transaction=True)
def test_authenticated_portal_pages_render_with_real_portal_tables(client, portal_tables):
    user = PortalUser.objects.create_user(
        username="ADMIN",
        password="prueba-segura",
        nombre_completo="Administrador de prueba",
        rol=PortalUser.ROLE_ADMIN,
    )
    client.force_login(user)
    version = CampaignVersion.objects.create(
        id_campana_origen=102,
        version=1,
        cod_plan="3668",
        nombre_campana="PROMO MIGRA PRE A POST",
        plan_minimo=Decimal("29.90"),
        plan_maximo=Decimal("29.90"),
        escenario="Migra Pre a Post",
        tipo_beneficio="MONTO_FIJO",
        valor_beneficio=Decimal("10.00"),
        periodo_meses=12,
        vigencia_ini=date(2026, 10, 1),
        vigencia_fin=date(2026, 10, 31),
        estado="A",
        usuario_creacion=user,
    )
    execution = ValidationExecution.objects.create(
        fecha_desde=date(2026, 10, 24),
        fecha_hasta=date(2026, 10, 24),
        tipo_ejecucion="MANUAL",
        estado="COMPLETADA",
        total_evaluados=1,
        total_correctos=1,
        usuario_ejecucion=user,
    )
    result = ValidationStoredResult.objects.create(
        ejecucion=execution,
        version=version,
        co_id=123456,
        linea="999999999",
        plan_monto=Decimal("29.90"),
        descuento_esperado=Decimal("10.00"),
        descuento_aplicado=Decimal("10.00"),
        diferencia=Decimal("0.00"),
        clasificacion="CORRECTO",
        codigo_motivo="DESCUENTO_CORRECTO",
        descripcion_motivo="Descuento validado conforme a la regla identificada.",
        evidencia_json='{"operacion":"Migra Pre a Post","campana":"PROMO MIGRA PRE A POST"}',
    )

    with patch("portal.views.list_effective_campaigns", return_value=[]):
        assert client.get(reverse("inicio")).status_code == 200
        assert client.get(reverse("campanas")).status_code == 200
    assert client.get(reverse("validaciones")).status_code == 200
    assert client.get(reverse("campaign_edit", args=[f"V-{version.pk}"])).status_code == 200
    assert client.get(reverse("validation_detail", args=[result.pk])).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_analyst_cannot_open_administration_actions(client, portal_tables):
    user = PortalUser.objects.create_user(
        username="ANALISTA",
        password="prueba-segura",
        nombre_completo="Analista de prueba",
        rol=PortalUser.ROLE_ANALYST,
    )
    client.force_login(user)

    assert client.get(reverse("campaign_create")).status_code == 403
    assert client.get(reverse("commercial_source")).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_administrator_can_create_campaign_and_start_validation(client, portal_tables):
    user = PortalUser.objects.create_user(
        username="ADMIN",
        password="prueba-segura",
        nombre_completo="Administrador de prueba",
        rol=PortalUser.ROLE_ADMIN,
    )
    client.force_login(user)
    campaign_data = {
        "identificador_comercial": "P-50",
        "nombre_campana": "CAMPAÑA DE PRUEBA",
        "operacion": "Portabilidad",
        "plan_minimo": "69.90",
        "plan_maximo": "99.90",
        "tipo_beneficio": "PORCENTAJE",
        "valor_beneficio": "50",
        "periodo_meses": "12",
        "vigencia_ini": "2026-10-01",
        "vigencia_fin": "2026-10-31",
        "estado": "A",
        "descripcion": "Regla autorizada para prueba",
    }
    with patch("portal.campaign_service.list_effective_campaigns", return_value=[]):
        response = client.post(reverse("campaign_create"), campaign_data)

    assert response.status_code == 302
    created = CampaignVersion.objects.get()
    assert created.valor_beneficio == Decimal("0.5000")
    assert ChangeAudit.objects.filter(entidad="CAMPANA", accion="CREAR").count() == 1

    with patch("portal.views.start_background_execution") as start:
        response = client.post(
            reverse("validation_start"),
            {"desde": "2026-10-24", "hasta": "2026-10-24"},
        )

    assert response.status_code == 302
    execution = ValidationExecution.objects.get()
    start.assert_called_once_with(execution.pk)
    assert ChangeAudit.objects.filter(entidad="EJECUCION", accion="EJECUTAR").count() == 1


def _commercial_workbook_bytes(campaign_name="CAMPAÑA AUTORIZADA"):
    output = BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Campañas"
    sheet.append(["Campaña", "Operación", "Beneficio"])
    sheet.append([campaign_name, "Portabilidad", "50%"])
    workbook.create_sheet("Actualizaciones")
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.mark.django_db(transaction=True)
def test_administrator_can_replace_commercial_workbook_with_audit(
    client, portal_tables, tmp_path
):
    user = PortalUser.objects.create_user(
        username="ADMIN",
        password="prueba-segura",
        nombre_completo="Administrador de prueba",
        rol=PortalUser.ROLE_ADMIN,
    )
    client.force_login(user)
    target = Path(tmp_path) / "Consolidado de Movil Masivo_Negocios.xlsx"
    upload = SimpleUploadedFile(
        "Consolidado actualizado.xlsx",
        _commercial_workbook_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with override_settings(COMMERCIAL_XLSX_PATH=target):
        response = client.post(
            reverse("commercial_source"),
            {"archivo": upload, "confirmacion": "on"},
        )
        replacement = SimpleUploadedFile(
            "Consolidado segunda version.xlsx",
            _commercial_workbook_bytes("CAMPAÑA ACTUALIZADA"),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        second_response = client.post(
            reverse("commercial_source"),
            {"archivo": replacement, "confirmacion": "on"},
        )

    assert response.status_code == 302
    assert second_response.status_code == 302
    assert target.is_file()
    assert target.with_name("Consolidado de Movil Masivo_Negocios.previous.xlsx").is_file()
    audits = ChangeAudit.objects.filter(entidad="FUENTE_COMERCIAL")
    assert audits.count() == 2
    assert all(audit.accion == "ACTUALIZAR" for audit in audits)
    assert all(audit.usuario == user for audit in audits)
