from django.core.files.uploadedfile import SimpleUploadedFile

from portal.forms import (
    CampaignForm,
    CommercialWorkbookUploadForm,
    ValidationRunForm,
)


def campaign_data(**changes):
    values = {
        "identificador_comercial": "3668",
        "nombre_campana": "PROMO MIGRA PRE A POST",
        "operacion": "Migra Pre a Post",
        "plan_minimo": "29.90",
        "plan_maximo": "29.90",
        "tipo_beneficio": "MONTO_FIJO",
        "valor_beneficio": "10.00",
        "periodo_meses": "12",
        "vigencia_ini": "2026-10-16",
        "vigencia_fin": "2026-10-31",
        "estado": "A",
        "descripcion": "S/ 10 por 12 meses",
        "tipo_filtro": "S",
    }
    values.update(changes)
    return values


def test_campaign_form_accepts_fixed_amount():
    form = CampaignForm(campaign_data())

    assert form.is_valid(), form.errors


def test_campaign_form_rejects_percentage_over_100():
    form = CampaignForm(
        campaign_data(tipo_beneficio="PORCENTAJE", valor_beneficio="100.01")
    )

    assert not form.is_valid()
    assert "valor_beneficio" in form.errors


def test_campaign_form_rejects_inverted_plan_and_dates():
    form = CampaignForm(
        campaign_data(
            plan_minimo="95.90",
            plan_maximo="79.90",
            vigencia_ini="2026-11-01",
            vigencia_fin="2026-10-31",
        )
    )

    assert not form.is_valid()
    assert {"plan_maximo", "vigencia_fin"} <= set(form.errors)


def test_validation_period_is_bounded():
    form = ValidationRunForm(
        {"desde": "2026-10-01", "hasta": "2026-11-01"},
        max_days=31,
    )

    assert not form.is_valid()
    assert "hasta" in form.errors


def test_commercial_workbook_form_rejects_non_xlsx_file():
    form = CommercialWorkbookUploadForm(
        {"confirmacion": "on"},
        {"archivo": SimpleUploadedFile("consolidado.xlsm", b"contenido")},
    )

    assert not form.is_valid()
    assert "archivo" in form.errors
