"""Lectura temporal de campañas para la fase sin persistencia aprobada."""

import csv
from pathlib import Path


class CampaignSourceUnavailable(RuntimeError):
    pass


def load_campaigns(path):
    source = Path(path)
    if not source.exists():
        raise CampaignSourceUnavailable(
            "El archivo de campañas todavía no está disponible en el servidor."
        )
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            required = {
                "ID_CAMPANA", "NOMBRE_CAMPANA", "PLAN_MINIMO", "PLAN_MAXIMO",
                "PERIODO", "PORCENTAJE", "ESCENARIO", "TIPO_FILTRO",
                "VIGENCIA_INI", "VIGENCIA_FIN", "ESTADO", "DESCRIPCION",
            }
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                raise CampaignSourceUnavailable(
                    "El archivo de campañas no contiene las columnas requeridas: "
                    + ", ".join(missing)
                )
            return [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except UnicodeError as error:
        raise CampaignSourceUnavailable(
            "El archivo de campañas no usa la codificación UTF-8 esperada."
        ) from error
