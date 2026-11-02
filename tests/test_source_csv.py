import pytest

from portal.source_csv import CampaignSourceUnavailable, load_campaigns
from portal.views import campaign_display


def test_reads_semicolon_utf8_campaign_source(tmp_path):
    path = tmp_path / "campaigns.csv"
    path.write_text(
        "ID_CAMPANA;COD_PLAN;NOMBRE_CAMPANA;PLAN_MINIMO;PLAN_MAXIMO;PERIODO;PORCENTAJE;ESCENARIO;DESCRIPCION;TIPO_FILTRO;VIGENCIA_INI;VIGENCIA_FIN;ESTADO\n"
        "102;3668;PROMO MIGRA PRE A POST;29.9;29.9;12;;Migra Pre a Post;S/10 x 12M;S;16/10/2026;31/10/2026;A\n",
        encoding="utf-8-sig",
    )
    rows = load_campaigns(path)
    assert rows[0]["ID_CAMPANA"] == "102"
    assert rows[0]["PORCENTAJE"] == ""


def test_rejects_missing_required_columns(tmp_path):
    path = tmp_path / "campaigns.csv"
    path.write_text("ID_CAMPANA;NOMBRE_CAMPANA\n1;A\n", encoding="utf-8")
    with pytest.raises(CampaignSourceUnavailable, match="columnas requeridas"):
        load_campaigns(path)


def test_percentage_is_presented_as_percent_without_changing_source():
    source = {"PORCENTAJE": "0.5", "DESCRIPCION": "50%"}
    displayed = campaign_display(source)
    assert displayed["BENEFICIO_DISPLAY"] == "50%"
    assert source["PORCENTAJE"] == "0.5"
