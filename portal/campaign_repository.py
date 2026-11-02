"""Repositorio de campañas: Oracle en servidor y CSV como alternativa controlada."""

from datetime import date, datetime
from decimal import Decimal

from django.db import DatabaseError, connection

from .source_csv import CampaignSourceUnavailable, load_campaigns


CAMPAIGN_SQL = """
SELECT
    ID_CAMPANA, COD_PLAN, NOMBRE_CAMPANA, PLAN_MINIMO, PLAN_MAXIMO,
    PERIODO, PORCENTAJE, ESCENARIO, DESCRIPCION, TIPO_FILTRO,
    DIA_INI, DIA_FIN, VIGENCIA_INI, VIGENCIA_FIN, ESTADO, FECHA_REGISTRO
FROM USRVALCBIO.CFG_CAMPANAS_PORTABILIDAD
ORDER BY ID_CAMPANA
"""


def _display_value(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value).strip()


def load_campaigns_from_oracle():
    try:
        with connection.cursor() as cursor:
            cursor.execute(CAMPAIGN_SQL)
            columns = [item[0] for item in cursor.description]
            return [
                {column: _display_value(value) for column, value in zip(columns, row)}
                for row in cursor.fetchall()
            ]
    except DatabaseError as error:
        raise CampaignSourceUnavailable(
            "No fue posible consultar la configuración de campañas en Oracle."
        ) from error


def load_configured_campaigns(settings):
    if settings.CAMPAIGN_SOURCE == "oracle":
        return load_campaigns_from_oracle()
    if settings.CAMPAIGN_SOURCE == "csv":
        return load_campaigns(settings.CAMPAIGNS_CSV_PATH)
    raise CampaignSourceUnavailable("CAMPAIGN_SOURCE debe ser oracle o csv.")
