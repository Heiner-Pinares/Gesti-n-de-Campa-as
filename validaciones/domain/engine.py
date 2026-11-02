"""Motor puro. No consulta Oracle ni escribe resultados."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum


MONEY = Decimal("0.01")


class BenefitType(StrEnum):
    PERCENTAGE = "PORCENTAJE"
    FIXED_AMOUNT = "MONTO_FIJO"


class ValidationStatus(StrEnum):
    CORRECT = "CORRECTO"
    ERROR = "ERROR"
    REVIEW = "POR_REVISAR"
    NOT_APPLICABLE = "NO_APLICA"


@dataclass(frozen=True)
class CampaignRule:
    rule_id: str
    campaign_name: str
    operation: str
    plan_min: Decimal
    plan_max: Decimal
    benefit_type: BenefitType
    benefit_value: Decimal
    duration_months: int
    valid_from: date
    valid_to: date
    active: bool = True
    plan_code: str | None = None

    def matches(self, case):
        return (
            self.active
            and _normalized_text(self.campaign_name) == _normalized_text(case.campaign_name)
            and _normalized_text(self.operation) == _normalized_text(case.operation)
            and self.plan_min <= case.plan_amount <= self.plan_max
            and self.valid_from <= case.eligibility_date <= self.valid_to
            and (
                not self.plan_code
                or not case.plan_code
                or _normalized_text(self.plan_code) == _normalized_text(case.plan_code)
            )
        )

    def expected_discount(self, plan_amount):
        if self.benefit_type == BenefitType.PERCENTAGE:
            value = plan_amount * self.benefit_value
        else:
            value = self.benefit_value
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ValidationCase:
    operation: str | None
    campaign_name: str | None
    plan_amount: Decimal | None
    eligibility_date: date | None
    applied_discount: Decimal | None
    plan_code: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    reason: str
    rule_id: str | None = None
    expected_discount: Decimal | None = None
    applied_discount: Decimal | None = None
    difference: Decimal | None = None
    code: str = ""


def _normalized_applied(value):
    if value is None:
        return None
    return abs(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _normalized_text(value):
    return " ".join(str(value or "").strip().casefold().split())


def validate_case(case, rules, tolerance=Decimal("0.01")):
    if not case.operation or not case.campaign_name or case.plan_amount is None:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Información insuficiente para identificar la regla aplicable.",
            code="DATOS_INCOMPLETOS",
        )
    if case.eligibility_date is None:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Fecha de elegibilidad no disponible.",
            code="FECHA_ELEGIBILIDAD_AUSENTE",
        )

    if case.plan_amount < 0:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Cargo de referencia inválido.",
            code="CARGO_INVALIDO",
        )

    matches = [rule for rule in rules if rule.matches(case)]
    if not matches:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Campaña sin una regla vigente identificable.",
            code="REGLA_NO_ENCONTRADA",
        )
    if len(matches) > 1:
        return ValidationResult(
            ValidationStatus.REVIEW,
            "Múltiples reglas aplicables sin una prioridad autorizada.",
            code="REGLAS_AMBIGUAS",
        )

    rule = matches[0]
    expected = rule.expected_discount(case.plan_amount)
    applied = _normalized_applied(case.applied_discount)
    if applied is None:
        return ValidationResult(
            ValidationStatus.ERROR,
            "Descuento requerido no encontrado.",
            rule_id=rule.rule_id,
            expected_discount=expected,
            code="DESCUENTO_AUSENTE",
        )

    difference = (applied - expected).quantize(MONEY, rounding=ROUND_HALF_UP)
    if abs(difference) <= tolerance:
        return ValidationResult(
            ValidationStatus.CORRECT,
            "Descuento validado conforme a la regla identificada.",
            rule_id=rule.rule_id,
            expected_discount=expected,
            applied_discount=applied,
            difference=difference,
            code="DESCUENTO_CORRECTO",
        )
    reason = "Descuento inferior al esperado." if difference < 0 else "Descuento superior al esperado."
    return ValidationResult(
        ValidationStatus.ERROR,
        reason,
        rule_id=rule.rule_id,
        expected_discount=expected,
        applied_discount=applied,
        difference=difference,
        code="DESCUENTO_INFERIOR" if difference < 0 else "DESCUENTO_SUPERIOR",
    )
