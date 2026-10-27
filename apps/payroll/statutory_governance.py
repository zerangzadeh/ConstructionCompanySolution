"""Explicit EXT-0018 non-production rules and reviewed employee opening facts.

Statutory values belong to source-linked policy versions, never this module.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import BusinessPermissionCode, Organization

from .models import PayrollRunEmployee, StatutoryPayrollContext

if TYPE_CHECKING:
    from apps.accounts.models import User

    from .statutory_services import EmployeeCalculation

POPULATION = "IR_LABOUR_ORDINARY_COMPULSORY"
PROFILE = "IR_SSO_ORDINARY_EMPLOYEE_1405"


def _hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def validate_governance(parameters: dict[str, Any], *, policy_code: str) -> None:
    """Versioned extension to schema1, restricted to the Human qualification scope."""
    g = parameters.get("statutory_governance")
    required = {
        "scope",
        "population",
        "insurance_profile",
        "tax_year_start",
        "tax_year_end",
        "review_reference",
        "review_sha256",
        "sources",
        "parameter_sources",
    }
    if not isinstance(g, dict) or set(g) != required:
        raise ValidationError("Explicit statutory governance envelope required.")
    if not settings.DEBUG or settings.SETTINGS_MODULE != "config.settings.development":
        raise ValidationError(
            "EXT-0018 qualification is authorized only in Development."
        )
    if (
        g["scope"] != "NON_PRODUCTION_QUALIFICATION"
        or g["population"] != POPULATION
        or g["insurance_profile"] != PROFILE
        or not g["review_reference"]
        or not _hash(g["review_sha256"])
    ):
        raise ValidationError("Unapproved scope, population, profile or review.")
    try:
        start, end = (
            date.fromisoformat(g["tax_year_start"]),
            date.fromisoformat(g["tax_year_end"]),
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError("Explicit tax-year dates required.") from exc
    if end <= start:
        raise ValidationError("Invalid tax-year interval.")
    sources = g["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValidationError("Retained statutory source hashes required.")
    refs = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {
            "reference",
            "sha256",
            "issued_on",
            "published_on",
            "effective_on",
            "supersedes",
            "treatment",
            "correction_requirement",
        }:
            raise ValidationError(
                "Source-specific date and supersession evidence required."
            )
        if (
            not source["reference"]
            or source["reference"] in refs
            or not _hash(source["sha256"])
        ):
            raise ValidationError("Source identity/hash invalid.")
        refs.add(source["reference"])
        for key in ("issued_on", "published_on", "effective_on"):
            try:
                date.fromisoformat(source[key])
            except (ValueError, TypeError) as exc:
                raise ValidationError("Ambiguous source date.") from exc
        if (
            source["treatment"] not in {"PROSPECTIVE", "RETROACTIVE"}
            or not source["correction_requirement"]
        ):
            raise ValidationError("Source-specific correction treatment required.")
    links = g["parameter_sources"]
    if not isinstance(links, dict) or set(links) != set(parameters) - {
        "statutory_governance"
    }:
        raise ValidationError(
            "Every runtime parameter must link to source/review evidence."
        )
    for values in links.values():
        if (
            not isinstance(values, list)
            or not values
            or not set(values) <= refs | {g["review_reference"]}
        ):
            raise ValidationError("Unknown statutory parameter source.")
    rounding = parameters["rounding"]
    if rounding != {
        "method": "ROUND_HALF_UP",
        "scale": 0,
        "stage": "FINAL_LIABILITY",
        "authority_type": "HUMAN_POLICY_WHERE_STATUTE_SILENT",
    }:
        raise ValidationError("The approved fallback rounding policy must be explicit.")
    if parameters["correction_mode"] != "source_version_governed":
        raise ValidationError("Universal successor-only semantics are not approved.")
    if (
        policy_code == "payroll-tax-regulatory"
        and parameters["calculation_basis"] != "CUMULATIVE_YTD"
    ):
        raise ValidationError("Annual cumulative tax computation required.")
    if (
        policy_code == "employee-insurance-regulatory"
        and parameters["basis_mode"] != "insured_remuneration_and_days"
    ):
        raise ValidationError(
            "Explicit remuneration and statutory work-day basis required."
        )


@transaction.atomic
def record_statutory_context(
    *,
    organization: Organization,
    actor: User,
    run_employee: PayrollRunEmployee,
    **facts: Any,
) -> StatutoryPayrollContext:
    """Record reviewed opening totals inclusive of all known earlier income/withholding.

    External amounts are additional current-period sources, explicitly including zero.
    Existing Payroll amounts remain the transaction authority; this is opening evidence.
    """
    from .statutory_services import _require

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW,
    )
    try:
        locked = PayrollRunEmployee.objects.select_for_update().get(
            pk=run_employee.pk, organization=organization
        )
    except PayrollRunEmployee.DoesNotExist as exc:
        raise PermissionDenied("Payroll result belongs to another tenant.") from exc
    # The employee lock also serializes statutory calculations across runs.
    type(locked.employee).objects.select_for_update().get(
        pk=locked.employee_id, organization=organization
    )
    result = StatutoryPayrollContext.objects.create(
        organization=organization, run_employee=locked, reviewed_by=actor, **facts
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_REVIEWED,
        entity_type="payroll.StatutoryPayrollContext",
        entity_id=result.pk,
        organization=organization,
        actor=actor,
        metadata={
            "run_employee_id": str(locked.pk),
            "evidence_digest": result.evidence_digest,
        },
    )
    return result


def reviewed_context(
    run_employee: PayrollRunEmployee, parameters: dict[str, Any]
) -> StatutoryPayrollContext:
    from .models import StatutoryCalculationKind, StatutoryEmployeeResult

    g = parameters["statutory_governance"]
    validate_governance(
        parameters,
        policy_code=(
            "payroll-tax-regulatory"
            if "calculation_basis" in parameters
            else "employee-insurance-regulatory"
        ),
    )
    type(run_employee.employee).objects.select_for_update().get(
        pk=run_employee.employee_id, organization=run_employee.organization
    )
    try:
        context = StatutoryPayrollContext.objects.get(
            run_employee=run_employee, organization=run_employee.organization
        )
    except StatutoryPayrollContext.DoesNotExist as exc:
        raise ValidationError(
            "Reviewed opening/YTD, external-income and population evidence required."
        ) from exc
    context.full_clean()
    if (
        context.population != g["population"]
        or context.insurance_profile != g["insurance_profile"]
        or str(context.tax_year_start) != g["tax_year_start"]
        or str(context.tax_year_end) != g["tax_year_end"]
    ):
        raise ValidationError("Unmapped population/profile or tax year.")
    if "calculation_basis" in parameters:
        later_or_overlapping = StatutoryEmployeeResult.objects.filter(
            organization=run_employee.organization,
            run_employee__employee_id=run_employee.employee_id,
            calculation__kind=StatutoryCalculationKind.PAYROLL_TAX,
            calculation__effective_on__gte=run_employee.run.period.starts_on,
            calculation__effective_on__lte=context.tax_year_end,
            calculation__successors__isnull=True,
        ).exclude(
            calculation__run_id__in=[
                run_employee.run_id,
                run_employee.run.replaces_id,
                run_employee.run.predecessor_id,
            ]
        )
        if later_or_overlapping.exists():
            raise ValidationError(
                "Overlapping/later withholding requires governed chronological reconciliation."
            )
        previous = list(
            StatutoryEmployeeResult.objects.filter(
                organization=run_employee.organization,
                run_employee__employee_id=run_employee.employee_id,
                calculation__kind=StatutoryCalculationKind.PAYROLL_TAX,
                calculation__effective_on__gte=context.tax_year_start,
                calculation__effective_on__lte=context.prior_through,
                calculation__successors__isnull=True,
            ).select_related("calculation")
        )
        prior_local_runs = PayrollRunEmployee.objects.filter(
            organization=run_employee.organization,
            employee_id=run_employee.employee_id,
            run__status="finalized",
            run__period__ends_on__gte=context.tax_year_start,
            run__period__ends_on__lte=context.prior_through,
        ).exclude(run__replacement_run__status="finalized")
        reconciled_run_ids = {result.calculation.run_id for result in previous}
        if prior_local_runs.exclude(run_id__in=reconciled_run_ids).exists():
            raise ValidationError(
                "Earlier finalized Payroll requires statutory reconciliation before YTD calculation."
            )
        known_income = Decimal(0)
        known_withholding = Decimal(0)
        for result in previous:
            snapshot = result.calculation_snapshot
            if "cumulative_taxable_income" not in snapshot:
                raise ValidationError(
                    "Prior non-cumulative calculation requires governed reconciliation."
                )
            known_income = max(
                known_income, Decimal(snapshot["cumulative_taxable_income"])
            )
            known_withholding = max(
                known_withholding,
                Decimal(snapshot["total_withholding_through_payment"]),
            )
        if (
            context.prior_taxable_income < known_income
            or context.prior_withholding < known_withholding
        ):
            raise ValidationError(
                "Opening/YTD cannot erase known prior income or withholding."
            )
    return context


def context_snapshot(context: StatutoryPayrollContext) -> dict[str, str]:
    names = (
        "tax_year_start",
        "tax_year_end",
        "prior_through",
        "prior_taxable_income",
        "prior_withholding",
        "external_taxable_income",
        "external_withholding",
        "population",
        "insurance_profile",
        "unemployment_covered",
        "work_days",
        "evidence_reference",
        "evidence_digest",
        "reviewed_by_id",
    )
    return {
        "id": str(context.pk),
        **{name: str(getattr(context, name)) for name in names},
    }


def calculate_governed(
    run_employee: PayrollRunEmployee,
    parameters: dict[str, Any],
    *,
    insurance: bool = False,
) -> EmployeeCalculation:
    """High precision until final liability; no fabricated rounding/statutory values."""
    from .statutory_services import (
        EmployeeCalculation,
        _decimal,
        _digest,
        _mapping,
        _round,
        _source_basis,
    )

    with localcontext() as arithmetic:
        arithmetic.prec = 60
        context = reviewed_context(run_employee, parameters)
        included, excluded, conditional, unsupported = (
            ("insurable", "non_insurable", "conditionally_insurable", "unsupported")
            if insurance
            else ("taxable", "non_taxable", "conditionally_taxable", "unsupported")
        )
        mapping = _mapping(
            parameters, allowed={included, excluded, conditional, unsupported}
        )
        for rule in mapping.values():
            if rule["classification"] in {conditional, unsupported}:
                # A separate reviewed effective policy must resolve the condition explicitly.
                raise ValidationError(
                    "Conditional/unreviewed components require a resolved source mapping."
                )
            if rule["basis_factor"] != (1 if rule["classification"] == included else 0):
                raise ValidationError(
                    "Component factor contradicts reviewed classification."
                )
        raw_basis, sources = _source_basis(run_employee, mapping)
        snapshot = {
            "context": context_snapshot(context),
            "source_lines": sources,
            "raw_basis": str(raw_basis),
        }
        if (
            parameters["thresholds"].get("floor") is not None
            or parameters["thresholds"].get("ceiling") is not None
        ):
            raise ValidationError(
                "Annual tax thresholds/daily insurance bounds must not be substituted."
            )
        if insurance:
            return _insurance(
                run_employee, parameters, context, raw_basis, snapshot, sources
            )
        if set(parameters["thresholds"]) != {"floor", "ceiling"}:
            raise ValidationError("Unsupported tax threshold semantics.")
        cumulative = (
            context.prior_taxable_income + context.external_taxable_income + raw_basis
        )
        exemption = Decimal(0)
        for row in parameters["exemptions"]:
            if set(row) != {"code", "amount"}:
                raise ValidationError("Explicit annual exemption required.")
            exemption += _decimal(
                row["amount"], name="annual exemption", minimum=Decimal(0)
            )
        basis = max(Decimal(0), cumulative - exemption)
        cursor, liability = Decimal(0), Decimal(0)
        bracket_evidence = []
        brackets = parameters["brackets"]
        if not brackets:
            raise ValidationError("Annual progressive brackets required.")
        for index, row in enumerate(brackets):
            if set(row) != {"lower", "upper", "rate"}:
                raise ValidationError("Invalid annual bracket.")
            lower = _decimal(row["lower"], name="lower", minimum=Decimal(0))
            upper = (
                None
                if row["upper"] is None
                else _decimal(row["upper"], name="upper", minimum=Decimal(0))
            )
            rate = _decimal(row["rate"], name="rate", minimum=Decimal(0))
            if (
                lower != cursor
                or rate > 100
                or (upper is not None and upper <= lower)
                or (upper is None and index != len(brackets) - 1)
            ):
                raise ValidationError("Annual bracket continuity invalid.")
            part = max(
                Decimal(0), min(basis, upper if upper is not None else basis) - lower
            )
            amount = part * rate / 100
            liability += amount
            bracket_evidence.append(
                {**row, "taxable_slice": str(part), "unrounded_liability": str(amount)}
            )
            cursor = upper if upper is not None else max(lower, basis)
        if brackets[-1]["upper"] is not None:
            raise ValidationError("Open final annual bracket required.")
        prior = context.prior_withholding + context.external_withholding
        outstanding = liability - prior
        if outstanding < 0:
            raise ValidationError(
                "Negative withholding requires a separately governed correction; no implicit refund."
            )
        withholding = _round(outstanding, parameters["rounding"])
        snapshot.update(
            calculation_basis="CUMULATIVE_YTD",
            cumulative_taxable_income=str(cumulative),
            exemption=str(exemption),
            basis=str(basis),
            cumulative_unrounded_liability=str(liability),
            prior_withholding=str(prior),
            total_withholding_through_payment=str(prior + withholding),
            annual_brackets=bracket_evidence,
            current_withholding=str(withholding),
        )
        line = {
            "line_code": "CUMULATIVE-YTD-WITHHOLDING",
            "classification": "tax_withholding",
            "payer": "employee",
            "basis_amount": basis,
            "rate": None,
            "unrounded_amount": outstanding,
            "amount": withholding,
            "evidence": {
                "annual_brackets": bracket_evidence,
                "prior_withholding": str(prior),
            },
        }
        return EmployeeCalculation(
            run_employee,
            basis,
            None,
            withholding,
            Decimal(0),
            Decimal(0),
            snapshot,
            _digest(snapshot),
            (line,),
        )


def _insurance(
    run_employee: PayrollRunEmployee,
    parameters: dict[str, Any],
    context: StatutoryPayrollContext,
    raw_basis: Decimal,
    snapshot: dict[str, Any],
    sources: list[dict],
) -> EmployeeCalculation:
    from .statutory_services import EmployeeCalculation, _decimal, _digest, _round

    bounds = parameters["thresholds"]
    if (
        set(bounds) != {"floor", "ceiling", "daily_minimum", "daily_maximum"}
        or parameters["exemptions"]
    ):
        raise ValidationError(
            "Explicit daily insurance bounds without undocumented exemptions required."
        )
    floor = _decimal(bounds["daily_minimum"], name="daily minimum", minimum=Decimal(0))
    ceiling = _decimal(bounds["daily_maximum"], name="daily maximum", minimum=floor)
    period = run_employee.run.period
    if context.work_days > (period.ends_on - period.starts_on).days + 1:
        raise ValidationError("Insured days exceed source period.")
    basis = min(max(raw_basis, floor * context.work_days), ceiling * context.work_days)
    categories = parameters["contribution_categories"]
    expected = {
        "SSO_EMPLOYEE": ("employee", Decimal(7)),
        "SSO_EMPLOYER": ("employer", Decimal(20)),
        "SSO_GOVERNMENT": ("other", Decimal(3)),
        "UNEMPLOYMENT": ("employer", Decimal(3)),
    }
    seen, lines = set(), []
    unrounded_totals = {
        "employee": Decimal(0),
        "employer": Decimal(0),
        "other": Decimal(0),
    }
    for row in categories:
        if set(row) != {"code", "payer", "rate"} or row["code"] in seen:
            raise ValidationError("Explicit unique insurance categories required.")
        code = row["code"]
        rate = _decimal(row["rate"], name="contribution", minimum=Decimal(0))
        if expected.get(code) != (row["payer"], rate):
            raise ValidationError(
                "Insurance category contradicts adopted ordinary profile."
            )
        seen.add(code)
        if code == "UNEMPLOYMENT" and not context.unemployment_covered:
            continue
        unrounded_totals[row["payer"]] += basis * rate / 100
    if seen != set(expected):
        raise ValidationError(
            "All profile categories and applicability must be explicit."
        )
    totals = {
        payer: _round(value, parameters["rounding"])
        for payer, value in unrounded_totals.items()
    }
    for payer, value in unrounded_totals.items():
        lines.append(
            {
                "line_code": "INSURANCE-" + payer.upper(),
                "classification": "insurance_contribution",
                "payer": payer,
                "basis_amount": basis,
                "rate": None,
                "unrounded_amount": value,
                "amount": totals[payer],
                "evidence": {
                    "categories": categories,
                    "unemployment_covered": context.unemployment_covered,
                },
            }
        )
    snapshot.update(
        basis=str(basis),
        work_days=context.work_days,
        categories=categories,
        unemployment_covered=context.unemployment_covered,
        totals={key: str(value) for key, value in totals.items()},
    )
    return EmployeeCalculation(
        run_employee,
        basis,
        Decimal(context.work_days),
        totals["employee"],
        totals["employer"],
        totals["other"],
        snapshot,
        _digest(snapshot),
        tuple(lines),
    )
