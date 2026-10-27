"""EXT-0018 adopted non-production calculations; employee facts are synthetic."""

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings

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

from . import test_cep052 as baseline
from .models import StatutoryPayrollContext
from .source_package_services import (
    activate_statutory_source_package,
    import_statutory_source_package,
)
from .statutory_governance import (
    calculate_governed,
    record_statutory_context,
    validate_governance,
)

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/governance/cep/evidence/CEP-069_EXT0018_REVIEW_REENTRY_20261027"
)


def parameters(insurance=False):
    return json.loads(
        (
            EVIDENCE
            / ("INSURANCE_PARAMETERS.json" if insurance else "TAX_PARAMETERS.json")
        ).read_text("utf-8")
    )


@override_settings(DEBUG=True, SETTINGS_MODULE="config.settings.development")
class AdoptedStatutoryTests(baseline.SourcePackageTests):
    def context(self, **changes):
        facts = {
            "tax_year_start": date(2026, 3, 21),
            "tax_year_end": date(2027, 3, 20),
            "prior_through": date(2026, 9, 22),
            "prior_taxable_income": Decimal(5000000000),
            "prior_withholding": Decimal(19000000),
            "external_taxable_income": Decimal(0),
            "external_withholding": Decimal(0),
            "population": "IR_LABOUR_ORDINARY_COMPULSORY",
            "insurance_profile": "IR_SSO_ORDINARY_EMPLOYEE_1405",
            "unemployment_covered": True,
            "work_days": 30,
            "evidence_reference": "Synthetic explicitly reviewed opening and external-income declaration; no live employee data",
            "evidence_digest": hashlib.sha256(
                b"synthetic opening declaration"
            ).hexdigest(),
        }
        facts.update(changes)
        return record_statutory_context(
            organization=self.organization,
            actor=self.actor,
            run_employee=self.run_employee,
            **facts,
        )

    def policy(
        self,
        *,
        insurance=False,
        version=1,
        predecessor=None,
        effective=date(2026, 3, 21),
        accepted=False,
    ):
        p = parameters(insurance)
        code = (
            "employee-insurance-regulatory" if insurance else "payroll-tax-regulatory"
        )
        spec = get_platform_policy_spec(code)
        policy, _ = PlatformPolicy.objects.get_or_create(
            code=code,
            defaults={
                "name": spec.name,
                "category": spec.category,
                "sensitivity": spec.sensitivity,
                "tenant_selectable": False,
                "created_by": self.platform,
                "updated_by": self.platform,
            },
        )
        result = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=version,
            parameters=p,
            effective_from=effective,
            effective_to=date(2027, 3, 21),
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            supersedes=predecessor,
            created_by=self.platform,
            reason="Isolated adopted source qualification",
        )
        g = p["statutory_governance"]
        for row in g["sources"]:
            source, _ = PolicySource.objects.get_or_create(
                source_identifier=row["reference"],
                version="EXT0018-reviewed-20261027",
                defaults={
                    "issuer": "Official issuing authority retained in reviewed source package",
                    "title": row["reference"],
                    "source_location": "Retained official source SHA256:"
                    + row["sha256"],
                    "publication_date": date.fromisoformat(row["published_on"]),
                    "effective_from": date.fromisoformat(row["effective_on"]),
                    "applicability": "Bounded ordinary population; source-specific treatment: "
                    + row["treatment"],
                    "reason": "Reviewed source-linked qualification",
                    "created_by": self.platform,
                },
            )
            PlatformPolicyVersionSource.objects.create(
                policy_version=result,
                source=source,
                linked_by=self.platform,
                reason="Retained source linkage",
            )
        common = {
            "policy_version": result,
            "reviewer_identity": "Human Decision Authority; direct adopted decision",
            "qualification_summary": "Human adoption is authority; no professional credentials asserted",
            "independence_statement": "AI-assisted implementation verification; no external professional independence asserted",
            "reviewed_on": date(2026, 10, 27),
            "review_scope": "Bounded non-production source mappings",
            "created_by": self.platform,
        }
        PolicyReviewEvidence.objects.create(
            **common,
            evidence_reference=g["review_reference"],
            disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
            conditions="ADOPTED_EXPERT_REVIEW.md conditions 1-10; Production excluded",
        )
        if accepted:
            PolicyReviewEvidence.objects.create(
                **common,
                evidence_reference="SYNTHETIC-TECHNICAL-CONDITIONS-FIXTURE",
                disposition=PolicyReviewDisposition.ACCEPTED,
                conditions="Test-only completed-condition fixture; not evidence that implementation passes",
            )
        payload = {
            "schema_version": 1,
            "ytd_treatment": {
                "source_reference": g["review_reference"],
                "description": "Explicit reviewed cumulative annual totals; missing history fails closed",
            },
            "retroactivity": {
                "source_reference": g["review_reference"],
                "description": "Source-specific dates and correction requirements; no finalized-history rewrite",
            },
            "evidence_references": [
                g["review_reference"],
                *[row["reference"] for row in g["sources"]],
            ],
        }
        return result, payload

    def calculate(self, insurance=False, **changes):
        p = parameters(insurance)
        p.update(changes)
        return calculate_governed(self.run_employee, p, insurance=insurance)

    def test_annual_ytd_subtracts_prior_withholding(self):
        self.context()
        result = self.calculate()
        # (5,000,001,000 - 4,800,000,000) * 10% - 19,000,000
        self.assertEqual(result.employee_amount, Decimal(1000100))
        self.assertEqual(
            result.snapshot["cumulative_taxable_income"], "5000001000.00000000"
        )
        self.assertEqual(len(result.lines), 1)

    def test_external_income_is_included(self):
        self.context(
            external_taxable_income=Decimal(100000000),
            external_withholding=Decimal(1000000),
        )
        self.assertEqual(self.calculate().employee_amount, Decimal(10000100))

    def test_missing_opening_rejects_even_when_current_pay_is_small(self):
        with self.assertRaisesMessage(ValidationError, "Reviewed opening"):
            self.calculate()

    def test_prior_local_payroll_without_statutory_reconciliation_rejects(self):
        from django.utils import timezone

        from .models import PayrollPeriod, PayrollRun, PayrollRunEmployee

        # Keep the earlier finalized source untouched; create the next period.
        period = PayrollPeriod.objects.create(
            organization=self.organization,
            code="NEXT-YTD",
            name="Next source period",
            starts_on=date(2026, 10, 23),
            ends_on=date(2026, 11, 22),
            cutoff_at=timezone.now(),
            status="finalized",
            finalized_at=timezone.now(),
            created_by=self.owner,
        )
        run = PayrollRun.objects.create(
            organization=self.organization,
            period=period,
            code="NEXT-YTD",
            status="finalized",
            idempotency_key="next-ytd",
            currency="IRR",
            monetary_policy_snapshot={"money_scale": 2},
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        row = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=run,
            employee=self.employee,
            status="finalized",
        )
        prior = self.run_employee
        self.run_employee = row
        self.context(prior_through=date(2026, 10, 22), work_days=31)
        with self.assertRaisesMessage(ValidationError, "Earlier finalized Payroll"):
            calculate_governed(row, parameters())
        self.run_employee = prior

    def test_explicit_zero_opening_is_permitted(self):
        self.context(prior_taxable_income=Decimal(0), prior_withholding=Decimal(0))
        self.assertEqual(self.calculate().employee_amount, 0)

    def test_unsupported_population_and_profile_reject(self):
        self.context(population="FOREIGN_NATIONAL")
        for insurance in (False, True):
            with self.assertRaisesMessage(ValidationError, "Unmapped population"):
                self.calculate(insurance)

    def test_unmapped_and_conditional_components_reject(self):
        self.context()
        p = parameters()
        for classification in ("unsupported", "conditionally_taxable"):
            p["component_mappings"][0]["classification"] = classification
            with self.assertRaises(ValidationError):
                calculate_governed(self.run_employee, p)
        p["component_mappings"][0]["component_code"] = "ANOTHER"
        p["component_mappings"][0]["classification"] = "taxable"
        with self.assertRaises(ValidationError):
            calculate_governed(self.run_employee, p)

    def test_tax_and_insurance_classifications_are_independent(self):
        self.context()
        tax = parameters()
        tax["component_mappings"][0].update(
            classification="non_taxable", basis_factor="0"
        )
        # Exercise independent dimensions with a synthetic classification only.
        self.assertEqual(
            calculate_governed(self.run_employee, tax).snapshot["raw_basis"], "0E-8"
        )
        self.assertGreater(self.calculate(True).employee_amount, 0)

    def test_final_rounding_does_not_round_bracket_slices(self):
        self.context(prior_taxable_income=Decimal(0), prior_withholding=Decimal(0))
        p = parameters()
        p["exemptions"] = []
        p["brackets"] = [
            {"lower": "0", "upper": "0.5", "rate": "50"},
            {"lower": "0.5", "upper": None, "rate": "50"},
        ]
        # 1000 * 50% = 500; per-slice rounding would produce 0+500=500,
        # use two .5 liabilities to expose the intermediate-rounding error.
        p["brackets"] = [
            {"lower": "0", "upper": "500", "rate": "0.1"},
            {"lower": "500", "upper": None, "rate": "0.1"},
        ]
        result = calculate_governed(self.run_employee, p)
        self.assertEqual(result.employee_amount, Decimal(1))
        self.assertEqual(
            result.snapshot["cumulative_unrounded_liability"], "1.000000000"
        )

    def test_negative_withholding_requires_governed_correction(self):
        self.context(prior_withholding=Decimal(30000000))
        with self.assertRaisesMessage(ValidationError, "Negative withholding"):
            self.calculate()

    def test_ordinary_profile_separates_government_and_employer_unemployment(self):
        self.context()
        result = self.calculate(True)
        self.assertEqual(result.basis, Decimal(166255500))
        self.assertEqual(result.employee_amount, Decimal(11637885))
        self.assertEqual(result.employer_amount, Decimal(38238765))
        self.assertEqual(result.other_amount, Decimal(4987665))

    def test_unemployment_exclusion_is_explicit(self):
        self.context(unemployment_covered=False)
        result = self.calculate(True)
        self.assertEqual(result.employer_amount, Decimal(33251100))
        self.assertEqual(result.employee_amount, Decimal(11637885))

    def test_workday_floor_29_30_and_ceiling(self):
        self.context(work_days=29)
        self.assertEqual(self.calculate(True).basis, Decimal(160713650))
        p = parameters(True)
        p["thresholds"]["daily_maximum"] = "5541850"
        self.assertEqual(
            calculate_governed(self.run_employee, p, insurance=True).basis,
            Decimal(160713650),
        )

    def test_context_tenant_permission_immutability(self):
        with self.assertRaises(PermissionDenied):
            record_statutory_context(
                organization=self.organization,
                actor=self.denied,
                run_employee=self.run_employee,
            )
        context = self.context()
        with self.assertRaises(ValidationError):
            context.save()
        with self.assertRaises(ValidationError):
            StatutoryPayrollContext.objects.filter(pk=context.pk).update(work_days=1)
        with self.assertRaises(ValidationError):
            context.delete()

    def test_governance_rejects_missing_source_dates_and_production(self):
        p = parameters()
        p["statutory_governance"]["sources"][0]["effective_on"] = None
        with self.assertRaises(ValidationError):
            validate_governance(p, policy_code="payroll-tax-regulatory")
        with (
            override_settings(DEBUG=False),
            self.assertRaisesMessage(ValidationError, "only in Development"),
        ):
            validate_governance(parameters(), policy_code="payroll-tax-regulatory")

    def test_human_conditional_approval_alone_cannot_import(self):
        policy, payload = self.policy()
        with self.assertRaises(ValidationError):
            import_statutory_source_package(
                actor=self.platform,
                policy_version=policy,
                payload=payload,
                reason="Pending conditions",
            )

    def test_explicit_source_linked_activation_and_calculation_snapshot(self):
        from .statutory_services import calculate_statutory

        self.context()
        policy, payload = self.policy(accepted=True)
        package = import_statutory_source_package(
            actor=self.platform,
            policy_version=policy,
            payload=payload,
            reason="Synthetic test verification",
        )
        activate_statutory_source_package(
            actor=self.platform,
            package=package,
            reason="Isolated synthetic verification",
        )
        result = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind="payroll_tax",
            reason="Fresh governed calculation",
        )
        self.assertEqual(result.employee_amount, Decimal(1000100))
        self.assertEqual(
            result.policy_snapshot["source_package_digest"], package.content_digest
        )
        self.assertEqual(
            result.employee_results.get().calculation_snapshot["context"][
                "evidence_digest"
            ],
            hashlib.sha256(b"synthetic opening declaration").hexdigest(),
        )
