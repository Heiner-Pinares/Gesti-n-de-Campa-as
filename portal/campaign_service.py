import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.db.models import Min

from .campaign_repository import load_configured_campaigns
from .models import CampaignVersion, ChangeAudit


class CampaignNotFound(LookupError):
    pass


class CampaignConflict(ValueError):
    pass


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        return None


def _date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    return None


def _conditions(version):
    if not version or not version.condiciones_json:
        return {}
    try:
        return json.loads(version.condiciones_json)
    except (TypeError, ValueError):
        return {}


def _source_record(row):
    percentage = _decimal(row.get("PORCENTAJE"))
    return {
        "origin_id": int(Decimal(row["ID_CAMPANA"])),
        "version_id": None,
        "version": 0,
        "record_key": f"O-{row['ID_CAMPANA']}",
        "source": "Oracle",
        "cod_plan": row.get("COD_PLAN") or "",
        "name": row.get("NOMBRE_CAMPANA") or "",
        "operation": row.get("ESCENARIO") or "",
        "plan_min": _decimal(row.get("PLAN_MINIMO")),
        "plan_max": _decimal(row.get("PLAN_MAXIMO")),
        "benefit_type": "PORCENTAJE" if percentage is not None else None,
        "benefit_value": percentage,
        "duration": int(_decimal(row.get("PERIODO")) or 0),
        "filter_type": row.get("TIPO_FILTRO") or "",
        "day_start": int(_decimal(row.get("DIA_INI")) or 0) or None,
        "day_end": int(_decimal(row.get("DIA_FIN")) or 0) or None,
        "valid_from": _date(row.get("VIGENCIA_INI")),
        "valid_to": _date(row.get("VIGENCIA_FIN")),
        "active": row.get("ESTADO") == "A",
        "description": row.get("DESCRIPCION") or "",
        "created_at": _date(row.get("FECHA_REGISTRO")),
    }


def _version_record(version):
    conditions = _conditions(version)
    return {
        "origin_id": int(version.id_campana_origen),
        "version_id": version.pk,
        "version": version.version,
        "record_key": f"V-{version.pk}",
        "source": "Portal",
        "cod_plan": version.cod_plan or "",
        "name": version.nombre_campana,
        "operation": version.escenario,
        "plan_min": version.plan_minimo,
        "plan_max": version.plan_maximo,
        "benefit_type": version.tipo_beneficio,
        "benefit_value": version.valor_beneficio,
        "duration": version.periodo_meses or 0,
        "filter_type": version.tipo_filtro or "",
        "day_start": version.dia_ini,
        "day_end": version.dia_fin,
        "valid_from": version.vigencia_ini,
        "valid_to": version.vigencia_fin,
        "active": version.estado == "A",
        "description": version.descripcion or "",
        "created_at": version.fecha_creacion,
        "modified_at": version.fecha_modificacion,
        "change_reason": conditions.get("motivo_modificacion", ""),
    }


def list_effective_campaigns(settings):
    sources = [_source_record(row) for row in load_configured_campaigns(settings)]
    latest = {}
    versions = CampaignVersion.objects.select_related("usuario_creacion").order_by(
        "id_campana_origen", "-version", "-id_version"
    )
    for version in versions:
        origin = int(version.id_campana_origen)
        latest.setdefault(origin, version)

    records = []
    source_origins = set()
    for source in sources:
        origin = source["origin_id"]
        source_origins.add(origin)
        records.append(_version_record(latest[origin]) if origin in latest else source)
    records.extend(
        _version_record(version)
        for origin, version in latest.items()
        if origin not in source_origins
    )
    return sorted(records, key=lambda item: (item["name"].casefold(), item["origin_id"]))


def campaign_history(origin_id):
    return list(
        CampaignVersion.objects.filter(id_campana_origen=origin_id)
        .select_related("usuario_creacion")
        .order_by("-version", "-id_version")
    )


def campaign_history_details(origin_id):
    versions = campaign_history(origin_id)
    version_ids = [item.pk for item in versions]
    audits = {
        int(item.id_entidad): item
        for item in ChangeAudit.objects.filter(
            entidad="CAMPANA", id_entidad__in=version_ids
        ).order_by("-fecha_evento")
    }
    labels = {
        "cod_plan": "identificador comercial",
        "name": "nombre",
        "operation": "operación",
        "plan_min": "plan mínimo",
        "plan_max": "plan máximo",
        "benefit_type": "tipo de beneficio",
        "benefit_value": "valor del beneficio",
        "duration": "duración",
        "valid_from": "vigencia inicial",
        "valid_to": "vigencia final",
        "active": "estado",
        "description": "descripción",
    }
    details = []
    for version in versions:
        audit = audits.get(version.pk)
        before = {}
        after = {}
        if audit:
            try:
                before = json.loads(audit.valor_anterior_json or "{}")
                after = json.loads(audit.valor_nuevo_json or "{}")
            except (TypeError, ValueError):
                pass
        changed = [
            label
            for key, label in labels.items()
            if before.get(key) != after.get(key)
        ]
        details.append(
            {
                "version": version,
                "reason": _conditions(version).get("motivo_modificacion", ""),
                "changed_fields": ", ".join(changed) or "Creación inicial",
            }
        )
    return details


def get_campaign(settings, record_key):
    try:
        kind, raw_id = record_key.split("-", 1)
        identifier = int(raw_id)
    except (ValueError, AttributeError) as error:
        raise CampaignNotFound("Campaña no encontrada.") from error
    if kind == "V":
        try:
            return _version_record(
                CampaignVersion.objects.select_related("usuario_creacion").get(pk=identifier)
            )
        except CampaignVersion.DoesNotExist as error:
            raise CampaignNotFound("Campaña no encontrada.") from error
    if kind == "O":
        for record in list_effective_campaigns(settings):
            if record["origin_id"] == identifier:
                return record
    raise CampaignNotFound("Campaña no encontrada.")


def campaign_form_initial(record):
    value = record.get("benefit_value")
    benefit_type = record.get("benefit_type")
    if benefit_type == "PORCENTAJE" and value is not None:
        value *= Decimal("100")
    if benefit_type is None:
        match = re.search(r"S/\s*(\d+(?:[.,]\d+)?)", record.get("description", ""), re.I)
        if match:
            benefit_type = "MONTO_FIJO"
            value = _decimal(match.group(1))
    return {
        "identificador_comercial": record.get("cod_plan"),
        "nombre_campana": record.get("name"),
        "operacion": record.get("operation"),
        "plan_minimo": record.get("plan_min"),
        "plan_maximo": record.get("plan_max"),
        "tipo_beneficio": benefit_type or "PORCENTAJE",
        "valor_beneficio": value,
        "periodo_meses": record.get("duration"),
        "vigencia_ini": record.get("valid_from"),
        "vigencia_fin": record.get("valid_to"),
        "estado": "A" if record.get("active") else "I",
        "descripcion": record.get("description"),
        "tipo_filtro": record.get("filter_type"),
        "dia_ini": record.get("day_start"),
        "dia_fin": record.get("day_end"),
    }


def _ranges_overlap(a_start, a_end, b_start, b_end):
    return a_start <= b_end and b_start <= a_end


def validate_no_ambiguous_overlap(settings, cleaned, excluded_origin=None):
    if cleaned["estado"] != "A":
        return
    name = " ".join(cleaned["nombre_campana"].casefold().split())
    operation = " ".join(cleaned["operacion"].casefold().split())
    for current in list_effective_campaigns(settings):
        if current["origin_id"] == excluded_origin or not current["active"]:
            continue
        if " ".join(current["name"].casefold().split()) != name:
            continue
        if " ".join(current["operation"].casefold().split()) != operation:
            continue
        if not current["valid_from"] or not current["valid_to"]:
            continue
        if current["plan_min"] is None or current["plan_max"] is None:
            continue
        if not _ranges_overlap(
            cleaned["vigencia_ini"], cleaned["vigencia_fin"],
            current["valid_from"], current["valid_to"],
        ):
            continue
        if _ranges_overlap(
            cleaned["plan_minimo"], cleaned["plan_maximo"],
            current["plan_min"], current["plan_max"],
        ):
            raise CampaignConflict(
                f"La regla se superpone con {current['name']} "
                f"({current['record_key']}) para el mismo rango y vigencia."
            )


def _serializable(record):
    return {
        key: (str(value) if isinstance(value, (Decimal, date, datetime)) else value)
        for key, value in record.items()
        if key not in {"created_at", "modified_at"}
    }


def save_campaign(settings, cleaned, user, previous=None, ip_address=None):
    excluded_origin = previous["origin_id"] if previous else None
    with transaction.atomic():
        if connection.vendor == "oracle":
            with connection.cursor() as cursor:
                cursor.execute(
                    "LOCK TABLE TBL_CAMPANA_VERSION_GC IN SHARE ROW EXCLUSIVE MODE"
                )
        validate_no_ambiguous_overlap(settings, cleaned, excluded_origin)

        if previous:
            origin = previous["origin_id"]
        else:
            minimum = CampaignVersion.objects.filter(
                id_campana_origen__lt=0
            ).aggregate(value=Min("id_campana_origen"))["value"]
            origin = int(minimum) - 1 if minimum is not None else -1

        current = (
            CampaignVersion.objects.filter(id_campana_origen=origin)
            .order_by("-version", "-id_version")
            .first()
        )
        if (
            previous
            and previous.get("version_id")
            and current
            and current.pk != previous["version_id"]
        ):
            raise CampaignConflict(
                "La campaña fue modificada por otro usuario. Recargue la página "
                "antes de guardar una nueva versión."
            )
        next_version = current.version + 1 if current else 1
        if current and current.estado == "A":
            current.estado = "I"
            current.save(update_fields=["estado", "fecha_modificacion"])

        value = cleaned["valor_beneficio"]
        if cleaned["tipo_beneficio"] == "PORCENTAJE":
            value = value / Decimal("100")
        conditions = {
            "motivo_modificacion": cleaned.get("motivo_modificacion", "").strip(),
            "fecha_elegibilidad": "VALIDO_DESDE",
        }
        created = CampaignVersion.objects.create(
            id_campana_origen=origin,
            version=next_version,
            cod_plan=cleaned.get("identificador_comercial") or None,
            nombre_campana=cleaned["nombre_campana"].strip(),
            plan_minimo=cleaned["plan_minimo"],
            plan_maximo=cleaned["plan_maximo"],
            escenario=cleaned["operacion"].strip(),
            tipo_beneficio=cleaned["tipo_beneficio"],
            valor_beneficio=value,
            periodo_meses=cleaned["periodo_meses"],
            tipo_filtro=cleaned.get("tipo_filtro") or None,
            dia_ini=cleaned.get("dia_ini"),
            dia_fin=cleaned.get("dia_fin"),
            vigencia_ini=cleaned["vigencia_ini"],
            vigencia_fin=cleaned["vigencia_fin"],
            estado=cleaned["estado"],
            descripcion=cleaned.get("descripcion") or None,
            condiciones_json=json.dumps(conditions, ensure_ascii=False),
            usuario_creacion=user,
        )
        new_record = _version_record(created)
        ChangeAudit.objects.create(
            entidad="CAMPANA",
            id_entidad=created.pk,
            accion="ACTUALIZAR" if previous else "CREAR",
            valor_anterior_json=(
                json.dumps(_serializable(previous), ensure_ascii=False) if previous else None
            ),
            valor_nuevo_json=json.dumps(_serializable(new_record), ensure_ascii=False),
            usuario=user,
            direccion_ip=ip_address,
        )
    return created


def effective_rule_records(settings):
    return list_effective_campaigns(settings)
