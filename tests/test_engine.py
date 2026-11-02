from datetime import date
from decimal import Decimal

from validaciones.domain import (
    BenefitType,
    CampaignRule,
    ValidationCase,
    ValidationStatus,
    validate_case,
)


def rule(**changes):
    values = {
        "rule_id": "R1",
        "campaign_name": "DTO PORTABILIDAD POSTPAGO",
        "operation": "Portabilidad",
        "plan_min": Decimal("69.90"),
        "plan_max": Decimal("289.90"),
        "benefit_type": BenefitType.PERCENTAGE,
        "benefit_value": Decimal("0.50"),
        "duration_months": 12,
        "valid_from": date(2026, 10, 1),
        "valid_to": date(2026, 10, 31),
    }
    values.update(changes)
    return CampaignRule(**values)


def case(**changes):
    values = {
        "operation": "Portabilidad",
        "campaign_name": "DTO PORTABILIDAD POSTPAGO",
        "plan_amount": Decimal("79.90"),
        "eligibility_date": date(2026, 10, 15),
        "applied_discount": Decimal("-39.95"),
    }
    values.update(changes)
    return ValidationCase(**values)


def test_percentage_discount_correct():
    result = validate_case(case(), [rule()])
    assert result.status == ValidationStatus.CORRECT
    assert result.expected_discount == Decimal("39.95")
    assert result.applied_discount == Decimal("39.95")


def test_percentage_discount_incorrect():
    result = validate_case(case(applied_discount=Decimal("-20.00")), [rule()])
    assert result.status == ValidationStatus.ERROR
    assert result.reason == "Descuento inferior al esperado."


def test_fixed_discount_correct():
    fixed = rule(
        rule_id="R2",
        campaign_name="PROMO MIGRA PRE A POST",
        operation="Migra Pre a Post",
        plan_min=Decimal("29.90"),
        plan_max=Decimal("29.90"),
        benefit_type=BenefitType.FIXED_AMOUNT,
        benefit_value=Decimal("10.00"),
    )
    result = validate_case(
        case(
            campaign_name="PROMO MIGRA PRE A POST",
            operation="Migra Pre a Post",
            plan_amount=Decimal("29.90"),
            applied_discount=Decimal("-10.00"),
        ),
        [fixed],
    )
    assert result.status == ValidationStatus.CORRECT
    assert result.expected_discount == Decimal("10.00")


def test_missing_required_discount_is_error():
    result = validate_case(case(applied_discount=None), [rule()])
    assert result.status == ValidationStatus.ERROR
    assert result.reason == "Descuento requerido no encontrado."


def test_unknown_rule_is_review():
    result = validate_case(case(campaign_name="CAMPAÑA SIN REGLA"), [rule()])
    assert result.status == ValidationStatus.REVIEW


def test_missing_eligibility_date_is_review():
    result = validate_case(case(eligibility_date=None), [rule()])
    assert result.status == ValidationStatus.REVIEW
    assert result.reason == "Fecha de elegibilidad no disponible."


def test_ambiguous_rules_are_review():
    result = validate_case(case(), [rule(), rule(rule_id="R2")])
    assert result.status == ValidationStatus.REVIEW
    assert "Múltiples" in result.reason


def test_plan_bounds_are_inclusive():
    lower = validate_case(
        case(plan_amount=Decimal("69.90"), applied_discount=Decimal("-34.95")),
        [rule()],
    )
    upper = validate_case(
        case(plan_amount=Decimal("289.90"), applied_discount=Decimal("-144.95")),
        [rule()],
    )
    assert lower.status == ValidationStatus.CORRECT
    assert upper.status == ValidationStatus.CORRECT


def test_rounding_uses_decimal_half_up():
    result = validate_case(
        case(plan_amount=Decimal("60.90"), applied_discount=Decimal("-30.45")),
        [rule(plan_min=Decimal("60.90"))],
    )
    assert result.expected_discount == Decimal("30.45")
