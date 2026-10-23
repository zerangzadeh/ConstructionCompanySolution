"""Read-only statutory prerequisites; no rule, package or schema activation."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError

from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
    PAYROLL_TAX_REGULATORY_POLICY_CODE,
    get_platform_policy_spec,
)

from .source_package_services import resolve_statutory_source_package


def statutory_prerequisites(*, on_date: date) -> list[dict[str, object]]:
    """Use the same resolvers as calculation/output, rather than row existence."""
    sources = {
        PAYROLL_TAX_REGULATORY_POLICY_CODE,
        EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    }
    result = []
    for code in [
        PAYROLL_TAX_REGULATORY_POLICY_CODE,
        EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
        PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
        EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    ]:
        spec = get_platform_policy_spec(code)
        resolver = (
            resolve_statutory_source_package
            if code in sources
            else resolve_effective_platform_regulatory_policy
        )
        try:
            resolver(code=code, consumer=spec.permitted_consumers[0], on_date=on_date)
        except ValidationError as exc:
            result.append(
                {
                    "label": spec.name,
                    "available": False,
                    "detail": "؛ ".join(exc.messages),
                }
            )
        else:
            result.append(
                {
                    "label": spec.name,
                    "available": True,
                    "detail": "نسخه مؤثر موجود است؛ کنترل اجرای انتخاب‌شده همچنان الزامی است.",
                }
            )
    return result
