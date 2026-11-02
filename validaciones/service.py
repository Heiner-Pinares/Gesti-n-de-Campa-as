import json
import threading
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from portal.campaign_service import effective_rule_records
from portal.models import ChangeAudit, ValidationExecution, ValidationStoredResult

from .domain import (
    BenefitType,
    CampaignRule,
    ValidationCase,
    ValidationResult,
    ValidationStatus,
    validate_case,
)
from .oracle_repository import iter_source_cases


ACTIVE_EXECUTION_STATES = ("PENDIENTE", "EN_PROCESO")


class DuplicateExecution(RuntimeError):
    pass


class InvalidExecutionPeriod(ValueError):
    pass


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def build_effective_rules(config=settings):
    rules = []
    version_by_rule = {}
    for record in effective_rule_records(config):
        if not record["active"] or not record["benefit_type"]:
            continue
        required = (
            record["name"], record["operation"], record["plan_min"],
            record["plan_max"], record["benefit_value"], record["valid_from"],
            record["valid_to"],
        )
        if any(value in (None, "") for value in required):
            continue
        rule_id = (
            f"VERSION-{record['version_id']}"
            if record["version_id"]
            else f"ORIGEN-{record['origin_id']}"
        )
        benefit_type = (
            BenefitType.PERCENTAGE
            if record["benefit_type"] == "PORCENTAJE"
            else BenefitType.FIXED_AMOUNT
        )
        rules.append(
            CampaignRule(
                rule_id=rule_id,
                campaign_name=record["name"],
                operation=record["operation"],
                plan_min=record["plan_min"],
                plan_max=record["plan_max"],
                benefit_type=benefit_type,
                benefit_value=record["benefit_value"],
                duration_months=record["duration"],
                valid_from=record["valid_from"],
                valid_to=record["valid_to"],
                active=record["active"],
                plan_code=record["cod_plan"] or None,
            )
        )
        version_by_rule[rule_id] = record["version_id"]
    return rules, version_by_rule


def _precondition_result(source):
    if int(source.get("cantidad_campanas") or 0) > 1:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Se encontraron varias campañas para el contrato y la emisión.",
            code="CAMPANAS_AMBIGUAS",
        )
    if int(source.get("cantidad_descuentos") or 0) > 1:
        raw_applied = _decimal(source.get("descuento_aplicado"))
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Se encontraron varios descuentos y no existe una regla de acumulación aprobada.",
            applied_discount=abs(raw_applied) if raw_applied is not None else None,
            code="DESCUENTOS_MULTIPLES",
        )
    prorated = _decimal(source.get("plan_prorrateo")) or Decimal("0")
    returned = _decimal(source.get("plan_devolucion")) or Decimal("0")
    if prorated != 0 or returned != 0:
        raw_applied = _decimal(source.get("descuento_aplicado"))
        return ValidationResult(
            ValidationStatus.REVIEW,
            "El registro contiene prorrateo o devolución y requiere una regla de cálculo confirmada.",
            applied_discount=abs(raw_applied) if raw_applied is not None else None,
            code="PRORRATEO_O_DEVOLUCION",
        )
    return None


def evaluate_source_case(source, rules, reason_map, tolerance):
    preliminary = _precondition_result(source)
    if preliminary:
        return preliminary
    reason = source.get("ch_reason")
    try:
        operation = reason_map.get(int(reason))
    except (TypeError, ValueError):
        operation = None
    case = ValidationCase(
        operation=operation,
        campaign_name=source.get("nombre_campana"),
        plan_amount=_decimal(source.get("plan_monto")),
        eligibility_date=_as_date(source.get("fecha_elegibilidad")),
        applied_discount=_decimal(source.get("descuento_aplicado")),
        plan_code=str(source.get("cod_plan") or "").strip() or None,
    )
    return validate_case(case, rules, tolerance=tolerance)


def _result_model(execution, source, result, version_by_rule, reason_map):
    try:
        operation = reason_map.get(int(source.get("ch_reason")))
    except (TypeError, ValueError):
        operation = None
    evidence = {
        "operacion": operation,
        "campana": source.get("nombre_campana"),
        "regla": result.rule_id,
        "fecha_elegibilidad": source.get("fecha_elegibilidad"),
        "fecha_activacion": source.get("fecha_activacion"),
        "motivo_alta": source.get("motivo_alta"),
        "codigo_plan": source.get("cod_plan"),
        "cantidad_campanas": int(source.get("cantidad_campanas") or 0),
        "cantidad_descuentos": int(source.get("cantidad_descuentos") or 0),
        "sncode_descuento": source.get("sncode_descuento"),
        "spcode_descuento": source.get("spcode_descuento"),
        "plan_prorrateo": source.get("plan_prorrateo"),
        "plan_devolucion": source.get("plan_devolucion"),
        "monto_con_igv": source.get("monto_con_igv"),
        "codigo_resultado": result.code,
    }
    applied = result.applied_discount
    if applied is None and source.get("descuento_aplicado") is not None:
        raw_applied = _decimal(source.get("descuento_aplicado"))
        applied = abs(raw_applied) if raw_applied is not None else None
    return ValidationStoredResult(
        ejecucion=execution,
        version_id=version_by_rule.get(result.rule_id),
        invoice_id=source.get("invoice_id"),
        invoicing_date=_as_date(source.get("invoicing_date")),
        co_id=source.get("co_id"),
        linea=str(source.get("linea") or "")[:30] or None,
        ch_reason=source.get("ch_reason"),
        plan_monto=_decimal(source.get("plan_monto")),
        descuento_esperado=result.expected_discount,
        descuento_aplicado=applied,
        diferencia=result.difference,
        clasificacion=result.status.value,
        codigo_motivo=result.code[:50],
        descripcion_motivo=result.reason[:1000],
        evidencia_json=json.dumps(evidence, ensure_ascii=False, default=_json_default),
    )


def create_execution(start, end, execution_type, user=None, ip_address=None):
    if start > end:
        raise InvalidExecutionPeriod("La fecha desde no puede ser posterior a la fecha hasta.")
    if (end - start).days + 1 > settings.VALIDATION_MAX_DAYS:
        raise InvalidExecutionPeriod(
            f"El periodo máximo es de {settings.VALIDATION_MAX_DAYS} días."
        )
    with transaction.atomic():
        if connection.vendor == "oracle":
            with connection.cursor() as cursor:
                cursor.execute(
                    "LOCK TABLE TBL_VALIDACION_EJECUCION_GC "
                    "IN SHARE ROW EXCLUSIVE MODE NOWAIT"
                )
        duplicate = ValidationExecution.objects.filter(
            fecha_desde=start,
            fecha_hasta=end,
            estado__in=ACTIVE_EXECUTION_STATES,
        ).first()
        if duplicate:
            raise DuplicateExecution(
                f"Ya existe una ejecución activa para ese periodo: #{duplicate.pk}."
            )
        execution = ValidationExecution.objects.create(
            fecha_desde=start,
            fecha_hasta=end,
            tipo_ejecucion=execution_type,
            estado="PENDIENTE",
            parametros_json=json.dumps(
                {"desde": start.isoformat(), "hasta": end.isoformat()},
                ensure_ascii=False,
            ),
            usuario_ejecucion=user,
        )
        ChangeAudit.objects.create(
            entidad="EJECUCION",
            id_entidad=execution.pk,
            accion="EJECUTAR",
            valor_nuevo_json=execution.parametros_json,
            usuario=user,
            direccion_ip=ip_address,
        )
    return execution


def execute_validation(execution_id, config=settings):
    execution = ValidationExecution.objects.get(pk=execution_id)
    execution.estado = "EN_PROCESO"
    execution.fecha_inicio = timezone.now()
    execution.mensaje_error = None
    execution.save(update_fields=["estado", "fecha_inicio", "mensaje_error"])
    counters = Counter()
    batch = []
    batch_size = max(1, int(config.VALIDATION_BATCH_SIZE))
    try:
        rules, version_by_rule = build_effective_rules(config)
        tolerance = Decimal(config.VALIDATION_TOLERANCE)
        source_rows = iter_source_cases(
            execution.fecha_desde,
            execution.fecha_hasta,
            tuple(config.VALIDATION_REASON_MAP),
            config.VALIDATION_EXCLUDED_SPCODES,
            batch_size=batch_size,
        )
        for source in source_rows:
            result = evaluate_source_case(
                source, rules, config.VALIDATION_REASON_MAP, tolerance
            )
            batch.append(
                _result_model(
                    execution, source, result, version_by_rule,
                    config.VALIDATION_REASON_MAP,
                )
            )
            counters[result.status.value] += 1
            if len(batch) >= batch_size:
                ValidationStoredResult.objects.bulk_create(batch, batch_size=batch_size)
                batch.clear()
                _update_progress(execution, counters)
        if batch:
            ValidationStoredResult.objects.bulk_create(batch, batch_size=batch_size)
        _finish_execution(execution, counters)
    except Exception as error:
        execution.estado = "ERROR"
        execution.fecha_fin = timezone.now()
        execution.mensaje_error = _safe_error_message(error)
        execution.save(update_fields=["estado", "fecha_fin", "mensaje_error"])
        raise
    return execution


def _update_progress(execution, counters):
    execution.total_evaluados = sum(counters.values())
    execution.total_correctos = counters[ValidationStatus.CORRECT.value]
    execution.total_errores = counters[ValidationStatus.ERROR.value]
    execution.total_revisar = counters[ValidationStatus.REVIEW.value]
    execution.total_no_aplica = counters[ValidationStatus.NOT_APPLICABLE.value]
    execution.save(
        update_fields=[
            "total_evaluados", "total_correctos", "total_errores",
            "total_revisar", "total_no_aplica",
        ]
    )


def _finish_execution(execution, counters):
    _update_progress(execution, counters)
    execution.estado = "COMPLETADA"
    execution.fecha_fin = timezone.now()
    execution.save(update_fields=["estado", "fecha_fin"])


def _safe_error_message(error):
    text = str(error).strip().splitlines()[0] if str(error).strip() else error.__class__.__name__
    return text[:1000]


def _background_target(execution_id):
    close_old_connections()
    try:
        try:
            execute_validation(execution_id)
        except Exception:
            # execute_validation ya conserva un estado ERROR y un mensaje seguro.
            pass
    finally:
        close_old_connections()


def start_background_execution(execution_id):
    thread = threading.Thread(
        target=_background_target,
        args=(execution_id,),
        name=f"validacion-gc-{execution_id}",
        daemon=True,
    )
    thread.start()
    return thread


def parse_evidence(value):
    try:
        return json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
