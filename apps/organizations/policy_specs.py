"""Closed, code-owned contracts for policies that may affect accounting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

ACCOUNTING_MONEY_PRECISION_POLICY_CODE = "accounting-money-precision"
ACCOUNTING_ROUNDING_POLICY_CODE = "accounting-rounding"
TREASURY_SELF_APPROVAL_POLICY_CODE = "treasury-self-approval"
SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE = "subledger-writeoff-self-approval"
RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE = "rfq-admissibility-self-approval"
RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE = "rfq-comparison-self-finalization"
RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE = "rfq-commercial-exception-self-approval"
RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE = (
    "rfq-sourcing-award-self-finalization"
)
RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE = "receivable-claim-regulatory"
TAXPAYER_INVOICE_REGULATORY_POLICY_CODE = "taxpayer-invoice-regulatory"
CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE = "contractor-compliance-regulatory"
PAYROLL_TAX_REGULATORY_POLICY_CODE = "payroll-tax-regulatory"
EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE = "employee-insurance-regulatory"
PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE = "payroll-tax-output-schema"
EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE = "employee-insurance-output-schema"
PROJECT_BUDGET_RESPONSE_POLICY_CODE = "project-controls-budget-overrun-response"
PROJECT_BUDGET_OVERRIDE_POLICY_CODE = "project-controls-budget-overrun-override-enabled"


@dataclass(frozen=True)
class PolicyFieldSpec:
    """A field contract supplied only after a Product Owner decision."""

    name: str
    value_type: type[object]
    allowed_values: tuple[object, ...] | None


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
    SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE: PlatformPolicySpec(
        code=SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
        name="خودتأییدی سوخت AP/AR",
        category="other",
        sensitivity="accounting",
        tenant_selectable=True,
        permitted_consumers=(
            "subledgers.writeoff.approve",
            "subledgers.writeoff.reverse",
        ),
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    PROJECT_BUDGET_RESPONSE_POLICY_CODE: PlatformPolicySpec(
        code=PROJECT_BUDGET_RESPONSE_POLICY_CODE,
        name="پاسخ به عبور از بودجه پروژه",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("project_controls.budget_overrun.evaluate",),
        fields=(PolicyFieldSpec("response", str, ("WARNING", "HARD_STOP")),),
        value_schema_approved=True,
    ),
    PROJECT_BUDGET_OVERRIDE_POLICY_CODE: PlatformPolicySpec(
        code=PROJECT_BUDGET_OVERRIDE_POLICY_CODE,
        name="امکان مجوز عبور از کنترل بودجه",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("project_controls.budget_overrun.evaluate",),
        fields=(PolicyFieldSpec("override_enabled", bool, (False, True)),),
        value_schema_approved=True,
    ),
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE: PlatformPolicySpec(
        code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
        name="دقت پول حسابداری",
        category="precision",
        sensitivity="accounting",
        tenant_selectable=True,
        permitted_consumers=(
            "accounting.journal.submit",
            "payroll.run.lock",
            "inventory.valuation.finalize",
        ),
        fields=(
            PolicyFieldSpec("money_scale", int, (0, 2)),
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
        permitted_consumers=(
            "accounting.journal.submit",
            "payroll.run.lock",
            "inventory.valuation.finalize",
        ),
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
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE: PlatformPolicySpec(
        code=RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
        name="خودتأییدی پذیرش تجاری پیشنهاد",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("procurement.quote_admissibility.approve",),
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE: PlatformPolicySpec(
        code=RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE,
        name="خودنهایی‌سازی مقایسه تجاری",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("procurement.comparison.finalize",),
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE: PlatformPolicySpec(
        code=RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE,
        name="خودتأییدی استثنای تجاری غیرمادی",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("procurement.commercial_exception.approve",),
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE: PlatformPolicySpec(
        code=RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE,
        name="خودنهایی‌سازی انتخاب تأمین‌کننده",
        category="other",
        sensitivity="operational",
        tenant_selectable=True,
        permitted_consumers=("procurement.sourcing_award.finalize",),
        fields=(PolicyFieldSpec("allow_self_approval", bool, (False, True)),),
        value_schema_approved=True,
    ),
    RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE: PlatformPolicySpec(
        code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
        name="قواعد مقرراتی صورت‌وضعیت دریافتنی",
        category="regulatory_rule_set",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("billing.progress_claim.calculate",),
        fields=(
            # None approves only the Decimal-string schema/range below, not a
            # statutory value. Publication still requires external provenance
            # and accepted professional review evidence.
            PolicyFieldSpec("tax_rate", str, None),
            PolicyFieldSpec("tax_basis", str, ("gross", "after_contractual")),
            PolicyFieldSpec("insurance_rate", str, None),
            PolicyFieldSpec("insurance_basis", str, ("gross", "after_contractual")),
        ),
        value_schema_approved=True,
    ),
    TAXPAYER_INVOICE_REGULATORY_POLICY_CODE: PlatformPolicySpec(
        code=TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
        name="قواعد صورتحساب مؤدیان",
        category="filing_export",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("billing.taxpayer_invoice.prepare",),
        fields=(
            # Values are never seeded. A reviewed external-authority version must
            # supply the statutory schema identity, exact field mapping and code.
            PolicyFieldSpec("schema_identifier", str, None),
            PolicyFieldSpec("submission_mode", str, ("export_only", "test_adapter")),
            PolicyFieldSpec("provider_key", str, None),
            PolicyFieldSpec("tax_code", str, None),
            PolicyFieldSpec("field_mapping", dict, None),
            PolicyFieldSpec("required_fields", list, None),
        ),
        value_schema_approved=True,
    ),
    CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE: PlatformPolicySpec(
        code=CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
        name="قواعد انطباق بیمه پیمانکار",
        category="insurance_regulatory",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("billing.contractor_compliance.calculate",),
        fields=(
            # The code validates shape only. Rates and clearance effects exist
            # solely in reviewed/published external-authority policy versions.
            PolicyFieldSpec("deduction_rate", str, None),
            PolicyFieldSpec("deduction_basis", str, ("gross", "net")),
            PolicyFieldSpec("clearance_required", bool, (False, True)),
            PolicyFieldSpec("schema_identifier", str, None),
        ),
        value_schema_approved=True,
    ),
    PAYROLL_TAX_REGULATORY_POLICY_CODE: PlatformPolicySpec(
        code=PAYROLL_TAX_REGULATORY_POLICY_CODE,
        name="قواعد مقرراتی مالیات حقوق",
        category="regulatory_rule_set",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("payroll.statutory_tax.calculate",),
        fields=(
            PolicyFieldSpec("component_mappings", list, None),
            PolicyFieldSpec("calculation_basis", str, None),
            PolicyFieldSpec("exemptions", list, None),
            PolicyFieldSpec("brackets", list, None),
            PolicyFieldSpec("thresholds", dict, None),
            PolicyFieldSpec("rounding", dict, None),
            PolicyFieldSpec("correction_mode", str, None),
        ),
        value_schema_approved=True,
    ),
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE: PlatformPolicySpec(
        code=EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
        name="قواعد مقرراتی بیمه کارکنان",
        category="insurance_regulatory",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("payroll.employee_insurance.calculate",),
        fields=(
            PolicyFieldSpec("component_mappings", list, None),
            PolicyFieldSpec("contribution_categories", list, None),
            PolicyFieldSpec("basis_mode", str, None),
            PolicyFieldSpec("thresholds", dict, None),
            PolicyFieldSpec("exemptions", list, None),
            PolicyFieldSpec("rounding", dict, None),
            PolicyFieldSpec("correction_mode", str, None),
        ),
        value_schema_approved=True,
    ),
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE: PlatformPolicySpec(
        code=PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
        name="طرح رسمی خروجی مالیات حقوق",
        category="filing_export",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("payroll.statutory_tax.output",),
        fields=(
            PolicyFieldSpec("schema_identifier", str, None),
            PolicyFieldSpec("official_identifiers", list, None),
            PolicyFieldSpec("calendar_mapping", dict, None),
            PolicyFieldSpec("monetary_scale", int, None),
            PolicyFieldSpec("field_mapping", dict, None),
            PolicyFieldSpec("required_fields", list, None),
            PolicyFieldSpec("encoding", str, None),
        ),
        value_schema_approved=True,
    ),
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE: PlatformPolicySpec(
        code=EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
        name="طرح رسمی فهرست بیمه کارکنان",
        category="filing_export",
        sensitivity="regulatory",
        tenant_selectable=False,
        permitted_consumers=("payroll.employee_insurance.output",),
        fields=(
            PolicyFieldSpec("schema_identifier", str, None),
            PolicyFieldSpec("official_identifiers", list, None),
            PolicyFieldSpec("calendar_mapping", dict, None),
            PolicyFieldSpec("monetary_scale", int, None),
            PolicyFieldSpec("field_mapping", dict, None),
            PolicyFieldSpec("required_fields", list, None),
            PolicyFieldSpec("encoding", str, None),
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
        raise ValidationError(
            "پارامترهای سیاست دقیقاً با قرارداد کد-محور هم‌خوان نیستند."
        )
    for field in spec.fields:
        value = parameters[field.name]
        if type(value) is not field.value_type or (
            field.allowed_values is not None and value not in field.allowed_values
        ):
            raise ValidationError(f"مقدار «{field.name}» در قرارداد سیاست مجاز نیست.")
        if field.allowed_values is None and field.name.endswith("_rate"):
            try:
                rate = Decimal(value)
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError(
                    f"مقدار «{field.name}» باید رشته Decimal معتبر باشد."
                ) from exc
            if not rate.is_finite() or rate < 0 or rate > 100:
                raise ValidationError(f"مقدار «{field.name}» باید بین صفر و صد باشد.")
    if spec.code == TAXPAYER_INVOICE_REGULATORY_POLICY_CODE:
        _validate_taxpayer_invoice_parameters(parameters)


def _validate_taxpayer_invoice_parameters(parameters: dict[str, object]) -> None:
    for name in ("schema_identifier", "provider_key", "tax_code"):
        if not str(parameters[name]).strip():
            raise ValidationError(f"مقدار «{name}» نمی‌تواند خالی باشد.")
    mapping = parameters["field_mapping"]
    required = parameters["required_fields"]
    if not mapping or not all(
        isinstance(key, str)
        and key.strip()
        and isinstance(value, str)
        and value.strip()
        for key, value in mapping.items()
    ):
        raise ValidationError("نگاشت فیلد صورتحساب باید رشته‌های غیرخالی داشته باشد.")
    if not required or not all(
        isinstance(value, str) and value.strip() for value in required
    ):
        raise ValidationError("فهرست فیلدهای الزامی صورتحساب معتبر نیست.")
    if len(set(required)) != len(required) or not set(required).issubset(mapping):
        raise ValidationError("فیلدهای الزامی باید یکتا و در نگاشت schema موجود باشند.")


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
