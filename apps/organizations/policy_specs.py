"""Closed, code-owned contracts for policies that may affect accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

ACCOUNTING_MONEY_PRECISION_POLICY_CODE = "accounting-money-precision"
ACCOUNTING_ROUNDING_POLICY_CODE = "accounting-rounding"
TREASURY_SELF_APPROVAL_POLICY_CODE = "treasury-self-approval"


@dataclass(frozen=True)
class PolicyFieldSpec:
    """A field contract supplied only after a Product Owner decision."""

    name: str
    value_type: type[object]
    allowed_values: tuple[object, ...]


@dataclass(frozen=True)
class PlatformPolicySpec:
    code: str
    name: str
    category: str
    sensitivity: str
    tenant_selectable: bool
    permitted_consumers: tuple[str, ...]
    fields: tuple[PolicyFieldSpec, ...]
    value_schema_approved: bool = False


# Product Owner decisions recorded on 2026-09-30. These are Product-defined
# technical/business values, not a claim of statutory or regulatory authority.
# A future change remains a new, effective-dated, historically pinned version.
PLATFORM_POLICY_SPECS: dict[str, PlatformPolicySpec] = {
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE: PlatformPolicySpec(
        code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
        name="دقت پول حسابداری",
        category="precision",
        sensitivity="accounting",
        tenant_selectable=True,
        permitted_consumers=("accounting.journal.submit",),
        fields=(
            PolicyFieldSpec("money_scale", int, (0,)),
            PolicyFieldSpec("intermediate_calculation_scale", int, (6,)),
            PolicyFieldSpec("preserve_unrounded_intermediates", bool, (True,)),
        ),
        value_schema_approved=True,
    ),
    ACCOUNTING_ROUNDING_POLICY_CODE: PlatformPolicySpec(
        code=ACCOUNTING_ROUNDING_POLICY_CODE,
        name="گرد کردن حسابداری",
        category="rounding",
        sensitivity="accounting",
        tenant_selectable=True,
        permitted_consumers=("accounting.journal.submit",),
        fields=(
            PolicyFieldSpec("rounding_method", str, ("ROUND_HALF_UP",)),
            PolicyFieldSpec("output_boundary", str, ("final_monetary_line",)),
            PolicyFieldSpec("tie_behavior", str, ("ROUND_HALF_UP",)),
        ),
        value_schema_approved=True,
    ),
    TREASURY_SELF_APPROVAL_POLICY_CODE: PlatformPolicySpec(
        code=TREASURY_SELF_APPROVAL_POLICY_CODE,
        name="خودتأییدی عملیات خزانه‌داری",
        category="other",
        sensitivity="accounting",
        tenant_selectable=True,
        permitted_consumers=("treasury.operation.approve",),
        fields=(
            PolicyFieldSpec("allow_self_approval", bool, (False, True)),
        ),
        value_schema_approved=True,
    ),
}

ACCOUNTING_INITIAL_POLICY_PARAMETERS: dict[str, dict[str, object]] = {
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE: {
        "money_scale": 0,
        "intermediate_calculation_scale": 6,
        "preserve_unrounded_intermediates": True,
    },
    ACCOUNTING_ROUNDING_POLICY_CODE: {
        "rounding_method": "ROUND_HALF_UP",
        "output_boundary": "final_monetary_line",
        "tie_behavior": "ROUND_HALF_UP",
    },
}


def get_platform_policy_spec(code: str) -> PlatformPolicySpec:
    try:
        return PLATFORM_POLICY_SPECS[code]
    except KeyError as exc:
        raise ValidationError("کد سیاست در کاتالوگ کد-محور مجاز نیست.") from exc


def initial_accounting_policy_parameters(code: str) -> dict[str, object]:
    """Return a copy of the Product Owner-approved initial policy values."""

    try:
        return ACCOUNTING_INITIAL_POLICY_PARAMETERS[code].copy()
    except KeyError as exc:
        raise ValidationError("کد سیاست حسابداری برای نسخه نخست مجاز نیست.") from exc


def validate_policy_parameters(*, spec: PlatformPolicySpec, parameters: object) -> None:
    if not spec.value_schema_approved:
        raise ValidationError(
            "schema و مقادیر این سیاست هنوز توسط مالک محصول تصویب نشده‌اند."
        )
    if not isinstance(parameters, dict):
        raise ValidationError("پارامترهای سیاست باید یک شیء JSON باشند.")
    expected = {field.name for field in spec.fields}
    if set(parameters) != expected:
        raise ValidationError("پارامترهای سیاست دقیقاً با قرارداد کد-محور هم‌خوان نیستند.")
    for field in spec.fields:
        value = parameters[field.name]
        if type(value) is not field.value_type or value not in field.allowed_values:
            raise ValidationError(f"مقدار «{field.name}» در قرارداد سیاست مجاز نیست.")


def validate_policy_for_consumer(
    *, policy_version: Any, consumer: str, expected_policy_code: str | None = None
) -> None:
    if expected_policy_code and policy_version.policy.code != expected_policy_code:
        raise ValidationError("کد سیاست با قرارداد مصرف‌کننده حسابداری هم‌خوان نیست.")
    spec = get_platform_policy_spec(policy_version.policy.code)
    if consumer not in spec.permitted_consumers:
        raise ValidationError("این مصرف‌کننده برای سیاست انتخاب‌شده مجاز نیست.")
    if (
        policy_version.policy.name != spec.name
        or policy_version.policy.category != spec.category
        or policy_version.policy.sensitivity != spec.sensitivity
        or policy_version.policy.tenant_selectable != spec.tenant_selectable
    ):
        raise ValidationError("تعریف ذخیره‌شده با قرارداد کد-محور سیاست هم‌خوان نیست.")
    validate_policy_parameters(spec=spec, parameters=policy_version.parameters)


def policy_version_is_configuration_ready(policy_version: Any) -> bool:
    try:
        validate_policy_parameters(
            spec=get_platform_policy_spec(policy_version.policy.code),
            parameters=policy_version.parameters,
        )
    except ValidationError:
        return False
    return True
