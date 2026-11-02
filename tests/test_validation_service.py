from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from validaciones.domain import ValidationStatus
from validaciones.oracle_repository import build_validation_query
from validaciones.service import (
    InvalidExecutionPeriod,
    build_effective_rules,
    create_execution,
    evaluate_source_case,
)


def record(**changes):
    values = {
        "origin_id": 10,
        "version_id": 3,
        "active": True,
        "benefit_type": "PORCENTAJE",
        "benefit_value": Decimal("0.50"),
        "name": "DTO PORTABILIDAD POSTPAGO",
        "operation": "Portabilidad",
        "plan_min": Decimal("69.90"),
        "plan_max": Decimal("289.90"),
        "duration": 12,
        "valid_from": date(2026, 10, 1),
        "valid_to": date(2026, 10, 31),
        "cod_plan": "",
    }
    values.update(changes)
    return values


def source(**changes):
    values = {
        "ch_reason": 2002,
        "nombre_campana": "DTO PORTABILIDAD POSTPAGO",
        "plan_monto": Decimal("79.90"),
        "fecha_elegibilidad": datetime(2026, 10, 15),
        "descuento_aplicado": Decimal("-39.95"),
        "cantidad_campanas": 1,
        "cantidad_descuentos": 1,
        "cod_plan": None,
    }
    values.update(changes)
    return values


def test_source_query_uses_binds_and_contains_no_commercial_case():
    sql, parameters = build_validation_query((21, 2002), (3674,))

    assert "CASE WHEN" not in sql.upper()
    assert ":reason_0" in sql and ":reason_1" in sql
    assert ":spcode_0" in sql
    assert parameters == {"reason_0": 21, "reason_1": 2002, "spcode_0": 3674}


def test_effective_rules_keep_portal_version(monkeypatch):
    monkeypatch.setattr("validaciones.service.effective_rule_records", lambda config: [record()])
    rules, versions = build_effective_rules(SimpleNamespace())

    assert len(rules) == 1
    assert rules[0].benefit_value == Decimal("0.50")
    assert rules[0].plan_code is None
    assert versions == {"VERSION-3": 3}


def test_different_source_product_identifier_does_not_block_confirmed_rule(monkeypatch):
    monkeypatch.setattr("validaciones.service.effective_rule_records", lambda config: [record(cod_plan="3021")])
    rules, _ = build_effective_rules(SimpleNamespace())

    result = evaluate_source_case(
        source(prod_offer="MaxIlim79_90SY_VM3One"),
        rules,
        {2002: "Portabilidad"},
        Decimal("0.01"),
    )

    assert result.status == ValidationStatus.CORRECT


def test_multiple_discounts_require_review():
    result = evaluate_source_case(
        source(cantidad_descuentos=2),
        [],
        {2002: "Portabilidad"},
        Decimal("0.01"),
    )

    assert result.status == ValidationStatus.REVIEW
    assert result.code == "DESCUENTOS_MULTIPLES"


def test_configured_case_is_evaluated_without_sql_case_when(monkeypatch):
    monkeypatch.setattr("validaciones.service.effective_rule_records", lambda config: [record()])
    rules, _ = build_effective_rules(SimpleNamespace())
    result = evaluate_source_case(
        source(), rules, {2002: "Portabilidad"}, Decimal("0.01")
    )

    assert result.status == ValidationStatus.CORRECT
    assert result.code == "DESCUENTO_CORRECTO"


def test_proration_does_not_block_advance_charge_validation(monkeypatch):
    monkeypatch.setattr("validaciones.service.effective_rule_records", lambda config: [record()])
    rules, _ = build_effective_rules(SimpleNamespace())
    result = evaluate_source_case(
        source(plan_prorrateo=Decimal("10.00")),
        rules,
        {2002: "Portabilidad"},
        Decimal("0.01"),
    )

    assert result.status == ValidationStatus.CORRECT
    assert result.code == "DESCUENTO_CORRECTO"


def test_devolution_requires_review_until_business_rule_is_confirmed():
    result = evaluate_source_case(
        source(plan_devolucion=Decimal("10.00")),
        [],
        {2002: "Portabilidad"},
        Decimal("0.01"),
    )

    assert result.status == ValidationStatus.REVIEW
    assert result.code == "DEVOLUCION_PENDIENTE"


def test_invalid_execution_period_is_rejected_before_database_access():
    try:
        create_execution(date(2026, 11, 2), date(2026, 11, 1), "MANUAL")
    except InvalidExecutionPeriod as error:
        assert "fecha desde" in str(error)
    else:
        raise AssertionError("El periodo invertido debió rechazarse.")
