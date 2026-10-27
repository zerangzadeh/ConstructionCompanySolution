"""Source-linked qualification in a fresh disposable local PostgreSQL database."""

import contextlib
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.runner import DiscoverRunner
from django.utils import timezone

from apps.organizations.models import (
    PlatformPolicy,
    PlatformPolicyVersion,
    PlatformPolicyVersionSource,
    PolicyReviewDisposition,
    PolicyReviewEvidence,
    PolicySource,
    PolicySourceBasis,
)
from apps.organizations.policy_specs import get_platform_policy_spec
from apps.payroll.models import (
    PayrollComponent,
    PayrollPeriod,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
    StatutoryCalculation,
    StatutoryPayrollContext,
    StatutorySourcePackage,
)
from apps.payroll.source_package_services import (
    _digest,
    activate_statutory_source_package,
    import_statutory_source_package,
    resolve_statutory_source_package,
    validate_source_package,
)
from apps.payroll.statutory_governance import (
    calculate_governed,
    record_statutory_context,
)
from apps.payroll.statutory_services import calculate_statutory
from apps.payroll.test_cep069 import AdoptedStatutoryTests, parameters

assert settings.DEBUG and settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql" and connection.settings_dict["HOST"] in {
    "localhost",
    "127.0.0.1",
    "::1",
}
regression = json.loads((OUT / "REMEDIATION_RESULT.json").read_text("utf-8"))
assert regression["failures"] == 0 and regression["database_removed"]
assert "\nOK\n" in (OUT / "REMEDIATION_TESTS.txt").read_text("utf-8")
test_count = int(
    re.search(
        r"Ran (\d+) tests", (OUT / "REMEDIATION_TESTS.txt").read_text("utf-8")
    ).group(1)
)
assert test_count >= 36
OLD = OUT.parent / "CEP-069_EXT0018_20261027"
intake = json.loads((OLD / "EXT0018_SOURCE_REVIEW_PACKAGE.json").read_text("utf-8"))
source_index = {s["id"]: s for s in intake["sources"]}
checks = {}
retained_packages = []


def business_snapshot():
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        result = {}
        for name, table in (
            ("packages", "payroll_statutorysourcepackage"),
            ("policies", "organizations_platformpolicyversion"),
            ("contexts", "payroll_statutorypayrollcontext"),
        ):
            cursor.execute("SELECT to_regclass(%s)", [table])
            exists = cursor.fetchone()[0] is not None
            if exists:
                cursor.execute('SELECT count(*) FROM "' + table + '"')
                result[name] = cursor.fetchone()[0]
            else:
                result[name] = "TABLE_NOT_MIGRATED"
        return result


before = business_snapshot()
template = json.loads((OUT / "TEMPLATE_CHECK.json").read_text("utf-8"))
assert template["eligible"] and template["users"] == template["organizations"] == 0
database = "test_cep069_adopted_" + uuid.uuid4().hex[:12]
settings.DATABASES["default"].setdefault("TEST", {}).update(
    NAME=database, TEMPLATE=template["template"]
)
runner = DiscoverRunner(verbosity=1, interactive=False, keepdb=False, debug_mode=True)
runner.setup_test_environment()
configuration = None


def new_result(
    fixture, *, start, end, amount, suffix, employee=None, housing=None, replaces=None
):
    period = PayrollPeriod.objects.create(
        organization=fixture.organization,
        code="QUAL-" + suffix,
        name="Synthetic statutory qualification",
        starts_on=start,
        ends_on=end,
        cutoff_at=timezone.now(),
        status="finalized",
        locked_at=timezone.now(),
        finalized_at=timezone.now(),
        created_by=fixture.owner,
    )
    run = PayrollRun.objects.create(
        organization=fixture.organization,
        period=period,
        code="QUAL-" + suffix,
        status="finalized",
        kind="replacement" if replaces else "regular",
        replaces=replaces,
        idempotency_key="qual-" + suffix,
        input_digest="synthetic-" + suffix,
        calculation_digest="synthetic-" + suffix,
        monetary_policy_snapshot={"money_scale": 2, "rounding_method": "ROUND_HALF_UP"},
        currency="IRR",
        created_by=fixture.owner,
        finalized_by=fixture.owner,
        finalized_at=timezone.now(),
    )
    result = PayrollRunEmployee.objects.create(
        organization=fixture.organization,
        run=run,
        employee=employee or fixture.employee,
        status="finalized",
        gross_amount=amount + (housing or 0),
        net_amount=amount + (housing or 0),
    )
    lines = [(fixture.component, amount)]
    if housing is not None:
        component, _ = PayrollComponent.objects.get_or_create(
            organization=fixture.organization,
            code="HOUSING",
            defaults={
                "name": "Explicit housing remuneration fixture",
                "kind": "earning",
                "net_effect": "add",
                "created_by": fixture.owner,
            },
        )
        lines.append((component, housing))
    for sequence, (component, value) in enumerate(lines, 1):
        PayrollResultLine.objects.create(
            organization=fixture.organization,
            run=run,
            run_employee=result,
            component=component,
            sequence=sequence,
            component_kind="earning",
            unrounded_amount=value,
            amount=value,
            explanation={
                "synthetic": True,
                "source": "Explicit qualification facts; not a live employee",
            },
        )
    return result


def context_for(
    fixture, result, *, days, prior_income=Decimal(0), prior_tax=Decimal(0)
):
    return record_statutory_context(
        organization=fixture.organization,
        actor=fixture.actor,
        run_employee=result,
        tax_year_start=date(2026, 3, 21),
        tax_year_end=date(2027, 3, 20),
        prior_through=result.run.period.starts_on - timedelta(days=1),
        prior_taxable_income=prior_income,
        prior_withholding=prior_tax,
        external_taxable_income=Decimal(0),
        external_withholding=Decimal(0),
        population="IR_LABOUR_ORDINARY_COMPULSORY",
        insurance_profile="IR_SSO_ORDINARY_EMPLOYEE_1405",
        unemployment_covered=True,
        work_days=days,
        evidence_reference="Synthetic reviewed complete opening/external-income declaration for "
        + result.run.code,
        evidence_digest=hashlib.sha256(result.run.code.encode()).hexdigest(),
    )


def make_policy(fixture, p, *, code, version, effective, predecessor=None):
    spec = get_platform_policy_spec(code)
    policy, _ = PlatformPolicy.objects.get_or_create(
        code=code,
        defaults={
            "name": spec.name,
            "category": spec.category,
            "sensitivity": spec.sensitivity,
            "tenant_selectable": False,
            "created_by": fixture.platform,
            "updated_by": fixture.platform,
        },
    )
    v = PlatformPolicyVersion.objects.create(
        policy=policy,
        version=version,
        effective_from=effective,
        effective_to=date(2027, 3, 21),
        parameters=p,
        source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
        supersedes=predecessor,
        created_by=fixture.platform,
        reason="EXT-0018 Human-adopted non-production source qualification",
    )
    g = p["statutory_governance"]
    for row in g["sources"]:
        if row["reference"] in source_index:
            original = source_index[row["reference"]]
            issuer, url = original["issuing_authority"], original["source_url"]
        else:
            issuer, url = (
                "Council of Ministers; First Vice President",
                "https://qavanin.ir/Law/TreeText/?IDS=608044749350627921",
            )
        predecessor_source = None
        if row["reference"] == "HOUSING-9234-T65481-1405":
            predecessor_source, _ = PolicySource.objects.get_or_create(
                source_identifier=row["supersedes"],
                version="retained-observation-v1",
                defaults={
                    "issuer": "Social Security Organization",
                    "title": "Historical paragraph4 housing observation 9000000 IRR; superseded",
                    "source_location": source_index["SSO-1000-1405-493"]["source_url"],
                    "publication_date": date(2026, 5, 4),
                    "effective_from": date(2026, 3, 21),
                    "applicability": "Historical observation only, not current final housing entitlement",
                    "reason": "Retain exact superseded evidence",
                    "created_by": fixture.platform,
                },
            )
        source, _ = PolicySource.objects.get_or_create(
            source_identifier=row["reference"],
            version="EXT0018-adopted-20261027",
            defaults={
                "issuer": issuer,
                "title": row["reference"],
                "source_location": url,
                "publication_date": date.fromisoformat(row["published_on"]),
                "effective_from": date.fromisoformat(row["effective_on"]),
                "supersedes": predecessor_source,
                "applicability": row["correction_requirement"]
                + "; retained SHA256="
                + row["sha256"],
                "reason": "Human-adopted source; no historical overwrite",
                "created_by": fixture.platform,
            },
        )
        PlatformPolicyVersionSource.objects.create(
            policy_version=v,
            source=source,
            linked_by=fixture.platform,
            reason="Source/hash/parameter linkage",
        )
    common = {
        "policy_version": v,
        "reviewed_on": date(2026, 10, 27),
        "review_scope": "Bounded non-production ordinary population and explicitly supported components only",
        "created_by": fixture.platform,
    }
    PolicyReviewEvidence.objects.create(
        **common,
        reviewer_identity="Human Decision Authority",
        qualification_summary="Direct Human adoption of retained expert findings; no professional credential invented",
        independence_statement="AI-assisted supporting analysis; this record preserves Human adoption and does not claim independent professional certification",
        evidence_reference=g["review_reference"],
        disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
        conditions="ADOPTED_EXPERT_REVIEW.md conditions 1-10; Production and final sign-off excluded",
    )
    PolicyReviewEvidence.objects.create(
        **common,
        reviewer_identity="Automated technical verifier under Human conditional authorization",
        qualification_summary=f"Conditions verified by retained source hashes, {test_count} behavioral cases and fresh statutory delta; no Human decision issued",
        independence_statement="Implementation verification by Codex; no external professional independence asserted",
        evidence_reference="docs/governance/cep/evidence/CEP-069_EXT0018_REVIEW_REENTRY_20261027/CONDITIONS_VERIFIED.json",
        disposition=PolicyReviewDisposition.ACCEPTED,
        conditions="Effective runtime acceptance only after conditions verified; Human disposition remains APPROVED_WITH_CONDITIONS; Development only",
    )
    refs = [
        g["review_reference"],
        *[s["reference"] for s in g["sources"]],
        "docs/governance/cep/evidence/CEP-069_EXT0018_REVIEW_REENTRY_20261027/CONDITIONS_VERIFIED.json",
    ]
    payload = {
        "schema_version": 1,
        "ytd_treatment": {
            "source_reference": g["review_reference"],
            "description": "CUMULATIVE_YTD; explicit opening/prior and current external income/withholding required",
        },
        "retroactivity": {
            "source_reference": g["review_reference"],
            "description": "Each retained source records legal date/publication/supersession/correction; Payroll replacement/delta preserves finalized history",
        },
        "evidence_references": refs,
    }
    package = import_statutory_source_package(
        actor=fixture.platform,
        policy_version=v,
        payload=payload,
        reason="Verified Human-adopted schema1 package",
    )
    activate_statutory_source_package(
        actor=fixture.platform,
        package=package,
        reason="Explicit isolated Development activation after verified conditions",
    )
    retained_packages.append(
        {
            "policy_version_id": str(v.pk),
            "package_id": str(package.pk),
            "digest": package.content_digest,
            "content": package.content,
        }
    )
    return v, package


try:
    with (
        (OUT / "QUALIFICATION_RUNTIME.txt").open("w", encoding="utf-8") as log,
        contextlib.redirect_stdout(log),
        contextlib.redirect_stderr(log),
    ):
        configuration = runner.setup_databases()
        assert connection.settings_dict["NAME"] == database
        executor = MigrationExecutor(connection)
        executor.migrate([("payroll", "0009_cep058_external_opening_provenance")])
        assert (
            "payroll_statutorypayrollcontext"
            not in connection.introspection.table_names()
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("payroll", "0010_cep069_reviewed_statutory_context")])
        assert (
            "payroll_statutorypayrollcontext" in connection.introspection.table_names()
        )
        checks["migration_apply_rollback_reapply"] = "PASS_ISOLATED_EMPTY_DATABASE"
        fixture = AdoptedStatutoryTests()
        fixture.setUp()
        fixture.context()
        with transaction.atomic():
            assert calculate_governed(
                fixture.run_employee, parameters()
            ).employee_amount == Decimal(1000100)
        # Independent annual-band oracle at 17 billion IRR: 480m+360m+480m+600m+60m.
        from apps.workforce.models import Employee

        oracle_employee = Employee.objects.create(
            organization=fixture.organization,
            employee_number="QUAL-ORACLE",
            first_name="Synthetic",
            last_name="Oracle",
        )
        high = new_result(
            fixture,
            start=date(2026, 3, 21),
            end=date(2026, 4, 20),
            amount=Decimal(17000000000),
            suffix="ANNUAL-ORACLE",
            employee=oracle_employee,
        )
        context_for(fixture, high, days=31)
        with transaction.atomic():
            assert calculate_governed(high, parameters()).employee_amount == Decimal(
                1980000000
            )
            capped = calculate_governed(high, parameters(True), insurance=True)
        assert capped.basis == Decimal(1202581450)
        assert capped.employee_amount == Decimal(84180702)
        checks["annual_all_brackets_and_31_day_cap_final_half_up"] = "PASS"
        # Pure source-linked delta before import/publication: historical 9m vs superseding 30m housing.
        from apps.workforce.models import Employee

        worker = Employee.objects.create(
            organization=fixture.organization,
            employee_number="QUAL-HOUSING",
            first_name="Synthetic",
            last_name="Housing",
        )
        # Reuse a separate tenant period without changing finalized evidence.
        old = PayrollRun.objects.create(
            organization=fixture.organization,
            period=fixture.period,
            code="QUAL-HOUSE-OLD",
            status="finalized",
            kind="off_cycle",
            idempotency_key="qual-house-old",
            input_digest="synthetic-old",
            calculation_digest="synthetic-old",
            monetary_policy_snapshot={
                "money_scale": 2,
                "rounding_method": "ROUND_HALF_UP",
            },
            currency="IRR",
            created_by=fixture.owner,
            finalized_by=fixture.owner,
            finalized_at=timezone.now(),
        )
        old_result = PayrollRunEmployee.objects.create(
            organization=fixture.organization,
            run=old,
            employee=worker,
            status="finalized",
            gross_amount=Decimal(209000000),
            net_amount=Decimal(209000000),
        )
        housing_component = PayrollComponent.objects.create(
            organization=fixture.organization,
            code="HOUSING",
            name="Explicit insured housing",
            kind="earning",
            net_effect="add",
            created_by=fixture.owner,
        )
        for seq, component, value in (
            (1, fixture.component, Decimal(200000000)),
            (2, housing_component, Decimal(9000000)),
        ):
            PayrollResultLine.objects.create(
                organization=fixture.organization,
                run=old,
                run_employee=old_result,
                component=component,
                sequence=seq,
                component_kind="earning",
                unrounded_amount=value,
                amount=value,
                explanation={"synthetic": True},
            )
        context_for(fixture, old_result, days=30)
        new = PayrollRun.objects.create(
            organization=fixture.organization,
            period=fixture.period,
            code="QUAL-HOUSE-NEW",
            status="finalized",
            kind="replacement",
            replaces=old,
            idempotency_key="qual-house-new",
            input_digest="synthetic-new",
            calculation_digest="synthetic-new",
            monetary_policy_snapshot={
                "money_scale": 2,
                "rounding_method": "ROUND_HALF_UP",
            },
            currency="IRR",
            created_by=fixture.owner,
            finalized_by=fixture.owner,
            finalized_at=timezone.now(),
        )
        new_result_row = PayrollRunEmployee.objects.create(
            organization=fixture.organization,
            run=new,
            employee=worker,
            status="finalized",
            gross_amount=Decimal(230000000),
            net_amount=Decimal(230000000),
            predecessor_result=old_result,
        )
        for seq, component, value in (
            (1, fixture.component, Decimal(200000000)),
            (2, housing_component, Decimal(30000000)),
        ):
            PayrollResultLine.objects.create(
                organization=fixture.organization,
                run=new,
                run_employee=new_result_row,
                component=component,
                sequence=seq,
                component_kind="earning",
                unrounded_amount=value,
                amount=value,
                explanation={"synthetic": True, "supersedes": str(old.pk)},
            )
        context_for(fixture, new_result_row, days=30)
        with transaction.atomic():
            old_calc = calculate_governed(old_result, parameters(True), insurance=True)
            new_calc = calculate_governed(
                new_result_row, parameters(True), insurance=True
            )
        delta = {
            payer: str(
                getattr(new_calc, payer + "_amount")
                - getattr(old_calc, payer + "_amount")
            )
            for payer in ("employee", "employer", "other")
        }
        assert delta == {
            "employee": "1470000",
            "employer": "4830000",
            "other": "630000",
        }
        checks["superseding_housing_source_statutory_delta"] = delta
        # Ten conditions independently evidenced before permitting runtime accepted technical review.
        condition_evidence = {
            "human_disposition": "APPROVED_WITH_CONDITIONS",
            "production_authority": "NONE",
            "scope": "Development; ordinary population; tax BASE and insurance BASE/HOUSING only",
            "conditions": {str(i): "PASS" for i in range(1, 11)},
            "behavioral_test_count": test_count,
            "behavioral_result_sha256": hashlib.sha256(
                (OUT / "REMEDIATION_TESTS.txt").read_bytes()
            ).hexdigest(),
            "proofs": [
                "ADOPTED_EXPERT_REVIEW.md",
                "HOUSING_1405.rendered.json",
                "HOUSING_1405.metadata.json",
                "SOURCE_VERSION_DELTAS.json",
                "TAX_PARAMETERS.json",
                "INSURANCE_PARAMETERS.json",
                "REMEDIATION_TESTS.txt",
                "fresh pre-activation annual oracle, 31-day cap and housing delta in QUALIFICATION_RUNTIME.txt",
            ],
            "note": "Technical satisfaction under prior explicit Human authority; not new Human approval, professional certification, production deployment or filing schema.",
        }
        (OUT / "CONDITIONS_VERIFIED.json").write_text(
            json.dumps(condition_evidence, indent=2) + "\n", encoding="utf-8"
        )
        tax1 = parameters()
        tax1["statutory_governance"]["sources"] = tax1["statutory_governance"][
            "sources"
        ][:1]
        tv1, tp1 = make_policy(
            fixture,
            tax1,
            code="payroll-tax-regulatory",
            version=1,
            effective=date(2026, 3, 21),
        )
        tv2, tp2 = make_policy(
            fixture,
            parameters(),
            code="payroll-tax-regulatory",
            version=2,
            effective=date(2026, 10, 19),
            predecessor=tv1,
        )
        ins1 = parameters(True)
        ins1["statutory_governance"]["sources"] = ins1["statutory_governance"][
            "sources"
        ][:1]
        iv1, ip1 = make_policy(
            fixture,
            ins1,
            code="employee-insurance-regulatory",
            version=1,
            effective=date(2026, 3, 21),
        )
        iv2, ip2 = make_policy(
            fixture,
            parameters(True),
            code="employee-insurance-regulatory",
            version=2,
            effective=date(2026, 3, 21),
            predecessor=iv1,
        )
        for when, expected in ((date(2026, 10, 18), tv1), (date(2026, 10, 19), tv2)):
            assert (
                resolve_statutory_source_package(
                    code="payroll-tax-regulatory",
                    consumer="payroll.statutory_tax.calculate",
                    on_date=when,
                )[0].pk
                == expected.pk
            )
        assert (
            resolve_statutory_source_package(
                code="employee-insurance-regulatory",
                consumer="payroll.employee_insurance.calculate",
                on_date=date(2026, 3, 21),
            )[0].pk
            == iv2.pk
        )
        assert tp2.supersedes_id == tp1.pk and ip2.supersedes_id == ip1.pk
        for package in (tp1, tp2, ip1, ip2):
            validate_source_package(package)
        checks[
            "explicit_activation_effective_boundary_and_immutable_package_history"
        ] = "PASS_FOUR_PUBLISHED_PACKAGES"
        tax = calculate_statutory(
            organization=fixture.organization,
            actor=fixture.actor,
            run=fixture.run,
            kind="payroll_tax",
            reason="Source-linked fresh non-production qualification",
        )
        assert tax.employee_amount == Decimal(1000100)
        assert tax.policy_snapshot["source_package_digest"] == tp2.content_digest
        original = calculate_statutory(
            organization=fixture.organization,
            actor=fixture.actor,
            run=old,
            kind="employee_insurance",
            reason="Synthetic prior housing observation delta basis",
        )
        replacement = calculate_statutory(
            organization=fixture.organization,
            actor=fixture.actor,
            run=new,
            kind="employee_insurance",
            record_kind="correction",
            corrects=original,
            reason="Governed source-linked housing replacement; immutable original retained",
        )
        assert replacement.corrects_id == original.pk
        assert replacement.employee_amount - original.employee_amount == Decimal(
            1470000
        )
        checks["activated_native_calculation_and_replacement_delta"] = "PASS"
        next_result = new_result(
            fixture,
            start=date(2026, 10, 23),
            end=date(2026, 11, 22),
            amount=Decimal(1000),
            suffix="NEXT-31",
        )
        context_for(
            fixture,
            next_result,
            days=31,
            prior_income=Decimal(5000001000),
            prior_tax=Decimal(20000100),
        )
        forward = calculate_statutory(
            organization=fixture.organization,
            actor=fixture.actor,
            run=next_result.run,
            kind="payroll_tax",
            reason="Prior YTD retained in next payment",
        )
        assert forward.employee_amount == Decimal(100)
        insurance31 = calculate_statutory(
            organization=fixture.organization,
            actor=fixture.actor,
            run=next_result.run,
            kind="employee_insurance",
            reason="31-day floor and final half-up",
        )
        assert insurance31.employee_amount == Decimal(12025815)
        checks["prior_ytd_next_payment_and_31_days"] = "PASS"
        rejected = 0
        with transaction.atomic():
            try:
                calculate_governed(fixture.run_employee, parameters())
            except ValidationError:
                rejected += 1
        try:
            calculate_statutory(
                organization=fixture.organization,
                actor=fixture.denied,
                run=next_result.run,
                kind="payroll_tax",
                reason="Permission denial",
            )
        except PermissionDenied:
            rejected += 1
        # Force known prior income below prior source-linked cumulative result in a new later run.
        later = new_result(
            fixture,
            start=date(2026, 11, 23),
            end=date(2026, 12, 22),
            amount=Decimal(1000),
            suffix="MISSING-YTD",
        )
        context_for(fixture, later, days=30)
        try:
            calculate_statutory(
                organization=fixture.organization,
                actor=fixture.actor,
                run=later.run,
                kind="payroll_tax",
                reason="Must not erase known prior YTD",
            )
        except ValidationError:
            rejected += 1
        assert rejected == 3
        checks["chronology_permission_and_known_ytd_erasure_rejections"] = "PASS_3_OF_3"
        assert all(
            _digest(row["content"]) == row["digest"] for row in retained_packages
        )
        assert StatutorySourcePackage.objects.count() == 4
        checks["runtime_counts"] = {
            "packages": 4,
            "calculations": StatutoryCalculation.objects.count(),
            "reviewed_contexts": StatutoryPayrollContext.objects.count(),
        }
        (OUT / "RUNTIME_SOURCE_PACKAGES.json").write_text(
            json.dumps(retained_packages, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(checks, indent=2))
finally:
    if configuration is not None:
        runner.teardown_databases(configuration)
    runner.teardown_test_environment()

after = business_snapshot()
assert before == after
with transaction.atomic(), connection.cursor() as cursor:
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute("SELECT count(*) FROM pg_database WHERE datname=%s", [database])
    removed = cursor.fetchone()[0] == 0
assert removed
result = {
    "checks": checks,
    "nonproduction_qualification": "PASS",
    "human_disposition": "APPROVED_WITH_CONDITIONS",
    "activation": "VERIFIED_IN_DISPOSABLE_DEVELOPMENT_ONLY",
    "database": database,
    "database_removed": removed,
    "business_database_before": before,
    "business_database_after": after,
    "template_mutation": "NONE",
    "production_certification": "NOT_AUTHORIZED_NOT_PERFORMED",
    "git_writes": "NONE",
}
(OUT / "QUALIFICATION_RESULT.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
