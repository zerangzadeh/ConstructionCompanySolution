from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    PlatformPolicy,
    PlatformPolicyVersion,
    PlatformPolicyVersionSource,
    PolicyReviewEvidence,
    PolicySource,
    PolicySourceBasis,
    PolicyVersionStatus,
)
from apps.organizations.models import (
    PolicyReviewDisposition as PlatformPolicyReviewDisposition,
)
from apps.organizations.policy_services import select_tenant_policy_version
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
    PAYROLL_TAX_REGULATORY_POLICY_CODE,
    get_platform_policy_spec,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import ProjectCostFact
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement
from apps.workforce.models import Employee

from .models import (
    ComponentKind,
    NetEffect,
    PayrollComponent,
    PayrollPeriod,
    PayrollPeriodStatus,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
    PayrollRunKind,
    PayrollRunStatus,
    ResultStatus,
    StatutoryCalculationKind,
    StatutoryExportStatus,
    StatutoryRecordKind,
    StatutoryReviewDisposition,
    StatutorySourcePackage,
)
from .source_package_services import _digest, package_content
from .statutory_services import (
    calculate_statutory,
    generate_statutory_output,
    record_export_evidence,
    record_statutory_identity,
    review_statutory_calculation,
)

STATUTORY_PERMISSIONS = [
    BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_CONFIGURATION_VIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE,
    BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_OUTPUT_GENERATE,
    BusinessPermissionCode.PAYROLL_STATUTORY_EXPORT,
    BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT,
    BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW,
]


class StatutoryPayrollTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="statutory-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Statutory Tenant", slug="statutory-tenant"
        )
        self.actor = self._member("statutory-operator", STATUTORY_PERMISSIONS)
        self.denied = self._member("general-payroll-only", [])
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="STAT-001",
            first_name="کارمند",
            last_name="قانونی",
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.organization,
            code="STAT-1405-07",
            name="دوره قانونی آزمون",
            starts_on=date(2026, 9, 23),
            ends_on=date(2026, 10, 22),
            cutoff_at=timezone.now(),
            status=PayrollPeriodStatus.FINALIZED,
            locked_at=timezone.now(),
            finalized_at=timezone.now(),
            created_by=self.owner,
        )
        self.run = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="STAT-RUN-01",
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="stat-run-01",
            input_digest="input-digest",
            calculation_digest="calculation-digest",
            monetary_policy_snapshot={
                "money_scale": 2,
                "rounding_method": "ROUND_HALF_UP",
            },
            currency=self.organization.settings.currency,
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        self.run_employee = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=self.run,
            employee=self.employee,
            status=ResultStatus.FINALIZED,
            gross_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
        )
        self.component = PayrollComponent.objects.create(
            organization=self.organization,
            code="BASE",
            name="مبنای آزمون",
            kind=ComponentKind.EARNING,
            net_effect=NetEffect.ADD,
            created_by=self.owner,
        )
        PayrollResultLine.objects.create(
            organization=self.organization,
            run=self.run,
            run_employee=self.run_employee,
            component=self.component,
            sequence=10,
            component_kind=ComponentKind.EARNING,
            basis=Decimal(1000),
            unrounded_amount=Decimal(1000),
            amount=Decimal("1000.00"),
            explanation={"fixture": True},
        )

    def _member(self, username: str, permissions: list[BusinessPermissionCode]) -> User:
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=username,
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[str(permission) for permission in permissions],
                is_active=True,
            )
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            assigned_by=OrganizationMembership.objects.get(
                organization=self.organization, user=self.owner
            ),
            approved_by=OrganizationMembership.objects.get(
                organization=self.organization, user=self.owner
            ),
            reason="Statutory test fixture",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            granted_by=OrganizationMembership.objects.get(
                organization=self.organization, user=self.owner
            ),
            approved_by=OrganizationMembership.objects.get(
                organization=self.organization, user=self.owner
            ),
            reason="Statutory test fixture",
        )
        return user

    def _tax_parameters(self, *, rate: str = "10") -> dict:
        return {
            "component_mappings": [
                {
                    "component_code": "BASE",
                    "classification": "taxable",
                    "basis_factor": "1",
                }
            ],
            "calculation_basis": "period",
            "exemptions": [{"code": "FIXTURE-EXEMPTION", "amount": "100"}],
            "brackets": [{"lower": "0", "upper": None, "rate": rate}],
            "thresholds": {"floor": None, "ceiling": None},
            "rounding": {"method": "ROUND_HALF_UP", "scale": 2, "stage": "line"},
            "correction_mode": "successor_only",
        }

    def _insurance_parameters(self) -> dict:
        return {
            "component_mappings": [
                {
                    "component_code": "BASE",
                    "classification": "insurable",
                    "basis_factor": "1",
                }
            ],
            "contribution_categories": [
                {"code": "FIXTURE-EMPLOYEE", "payer": "employee", "rate": "7"},
                {"code": "FIXTURE-EMPLOYER", "payer": "employer", "rate": "20"},
                {"code": "FIXTURE-OTHER", "payer": "other", "rate": "3"},
            ],
            "basis_mode": "wage",
            "thresholds": {"floor": None, "ceiling": None},
            "exemptions": [],
            "rounding": {"method": "ROUND_HALF_UP", "scale": 2, "stage": "line"},
            "correction_mode": "successor_only",
        }

    def _schema_parameters(
        self, identifier: str, official_identifiers: tuple[str, ...] = ()
    ) -> dict:
        parameters = {
            "schema_identifier": identifier,
            "official_identifiers": list(official_identifiers),
            "calendar_mapping": {"mode": "gregorian_iso"},
            "monetary_scale": 2,
            "field_mapping": {
                "personnel_no": "employee_number",
                "basis": "basis_amount",
                "employee_share": "employee_amount",
                "employer_share": "employer_amount",
                "other_share": "other_amount",
                "total": "total_amount",
            },
            "required_fields": ["personnel_no", "basis", "total"],
            "encoding": "UTF-8",
        }
        parameters["field_mapping"].update({key: key for key in official_identifiers})
        parameters["required_fields"].extend(official_identifiers)
        return parameters

    def _published_policy(
        self,
        code: str,
        parameters: dict,
        *,
        version: int = 1,
        effective_from: date = date(2026, 1, 1),
    ):
        spec = get_platform_policy_spec(code)
        policy, _ = PlatformPolicy.objects.get_or_create(
            code=code,
            defaults={
                "name": spec.name,
                "category": spec.category,
                "sensitivity": spec.sensitivity,
                "tenant_selectable": spec.tenant_selectable,
                "requires_source_provenance": False,
                "created_by": self.owner,
                "updated_by": self.owner,
            },
        )
        policy_version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=version,
            parameters=parameters,
            effective_from=effective_from,
            status=PolicyVersionStatus.DRAFT,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            created_by=self.owner,
            reason="Source-backed test fixture; not a statutory assertion",
        )
        source = PolicySource.objects.create(
            issuer=f"Fixture authority {code}",
            title="Controlled source fixture",
            source_identifier=f"{code}-{version}",
            version=str(version),
            publication_date=date(2026, 1, 1),
            effective_from=effective_from,
            applicability="Test-only deterministic statutory framework",
            reason="Test fixture",
            created_by=self.owner,
        )
        PlatformPolicyVersionSource.objects.create(
            policy_version=policy_version,
            source=source,
            linked_by=self.owner,
            reason="Test fixture source link",
        )
        PolicyReviewEvidence.objects.create(
            policy_version=policy_version,
            reviewer_identity="Qualified fixture reviewer",
            qualification_summary="Test-only review evidence",
            independence_statement="Recorded for test boundary",
            evidence_reference=f"REVIEW-{code}-{version}",
            reviewed_on=date(2026, 1, 2),
            review_scope="Exact fixture parameters",
            disposition=PlatformPolicyReviewDisposition.ACCEPTED,
            created_by=self.owner,
        )
        if code in {
            PAYROLL_TAX_REGULATORY_POLICY_CODE,
            EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
        }:
            # Synthetic evidence, never a current Iranian statutory assertion.
            content = package_content(
                policy=policy_version,
                payload={
                    "schema_version": 1,
                    "ytd_treatment": {
                        "source_reference": source.source_identifier,
                        "description": "Period fixture only; cumulative calculation stays gated",
                    },
                    "retroactivity": {
                        "source_reference": source.source_identifier,
                        "description": "Explicit successor-only fixture policy",
                    },
                    "evidence_references": [source.source_identifier],
                },
            )
            StatutorySourcePackage.objects.create(
                policy_version=policy_version,
                schema_version=1,
                content=content,
                content_digest=_digest(content),
                imported_by=self.owner,
                reason="Synthetic test fixture",
            )
        PlatformPolicyVersion.objects.filter(pk=policy_version.pk).update(
            status=PolicyVersionStatus.PUBLISHED,
            published_by=self.owner,
            published_at=timezone.now(),
        )
        return PlatformPolicyVersion.objects.get(pk=policy_version.pk)

    def test_missing_authority_and_incomplete_component_mapping_fail_closed(self):
        with self.assertRaises(ValidationError):
            calculate_statutory(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="No authority",
            )
        parameters = self._tax_parameters()
        parameters["component_mappings"] = [
            {
                "component_code": "OTHER",
                "classification": "taxable",
                "basis_factor": "1",
            }
        ]
        self._published_policy(PAYROLL_TAX_REGULATORY_POLICY_CODE, parameters)
        with self.assertRaises(ValidationError):
            calculate_statutory(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="Incomplete mapping",
            )

    def test_published_policy_without_source_and_review_fails_closed(self):
        spec = get_platform_policy_spec(PAYROLL_TAX_REGULATORY_POLICY_CODE)
        policy = PlatformPolicy.objects.create(
            code=spec.code,
            name=spec.name,
            category=spec.category,
            sensitivity=spec.sensitivity,
            tenant_selectable=False,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters=self._tax_parameters(),
            effective_from=date(2026, 1, 1),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            created_by=self.owner,
            published_by=self.owner,
            published_at=timezone.now(),
            reason="Deliberately incomplete authority fixture",
        )
        with self.assertRaises(ValidationError):
            calculate_statutory(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="Must fail",
            )

    def test_tax_and_employee_insurance_are_decimal_version_pinned_and_independent(
        self,
    ):
        tax_policy = self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        insurance_policy = self._published_policy(
            EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
            self._insurance_parameters(),
        )
        tax = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind=StatutoryCalculationKind.PAYROLL_TAX,
            reason="Tax fixture",
        )
        insurance = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind=StatutoryCalculationKind.EMPLOYEE_INSURANCE,
            reason="Insurance fixture",
        )
        self.assertEqual(tax.policy_version, tax_policy)
        self.assertEqual(tax.total_basis, Decimal(900))
        self.assertEqual(tax.employee_amount, Decimal("90.00"))
        self.assertEqual(insurance.policy_version, insurance_policy)
        self.assertEqual(insurance.total_basis, Decimal(1000))
        self.assertEqual(insurance.employee_amount, Decimal("70.00"))
        self.assertEqual(insurance.employer_amount, Decimal("200.00"))
        self.assertEqual(insurance.other_amount, Decimal("30.00"))
        self.assertNotEqual(tax.policy_version_id, insurance.policy_version_id)
        self.assertEqual(tax.policy_snapshot["parameters"], self._tax_parameters())
        self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE,
            self._tax_parameters(rate="11"),
            version=2,
            effective_from=date(2027, 1, 1),
        )
        tax.refresh_from_db()
        self.assertEqual(tax.policy_version, tax_policy)
        self.assertEqual(tax.employee_amount, Decimal("90.00"))
        review_statutory_calculation(
            organization=self.organization,
            actor=self.actor,
            calculation=insurance,
            disposition=StatutoryReviewDisposition.ACCEPTED,
            reason="Insurance reviewed fixture",
        )
        insurance_schema = self._published_policy(
            EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
            self._schema_parameters(
                "TEST-INSURANCE-SCHEMA-V1",
                ("employer_workshop_id", "employee_insurance_id"),
            ),
        )
        employer_identity = record_statutory_identity(
            organization=self.organization,
            actor=self.actor,
            kind=StatutoryCalculationKind.EMPLOYEE_INSURANCE,
            schema_version=insurance_schema,
            identifiers={"employer_workshop_id": "FIXTURE-WORKSHOP"},
            effective_from=date(2026, 1, 1),
            source_reference="source-backed employer fixture",
        )
        employee_identity = record_statutory_identity(
            organization=self.organization,
            actor=self.actor,
            kind=StatutoryCalculationKind.EMPLOYEE_INSURANCE,
            schema_version=insurance_schema,
            employee=self.employee,
            identifiers={"employee_insurance_id": "FIXTURE-EMPLOYEE-ID"},
            effective_from=date(2026, 1, 1),
            source_reference="source-backed employee fixture",
        )
        insurance_output = generate_statutory_output(
            organization=self.organization,
            actor=self.actor,
            calculation=insurance,
            output_identifier="INSURANCE-OUT-01",
        )
        self.assertEqual(insurance_output.schema_version, insurance_schema)
        self.assertEqual(insurance_output.reconciliation.status, "matched")
        self.assertEqual(
            set(insurance_output.schema_snapshot["identity_evidence_ids"]),
            {str(employer_identity.pk), str(employee_identity.pk)},
        )
        with self.assertRaises(ValidationError):
            tax.save()
        self.assertFalse(hasattr(insurance, "contractor_assessment"))

    def test_schema_output_export_idempotency_reconciliation_and_immutability(self):
        self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        calculation = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind=StatutoryCalculationKind.PAYROLL_TAX,
            reason="Tax fixture",
        )
        review_statutory_calculation(
            organization=self.organization,
            actor=self.actor,
            calculation=calculation,
            disposition=StatutoryReviewDisposition.ACCEPTED,
            reason="Reviewed fixture",
        )
        with self.assertRaises(ValidationError):
            generate_statutory_output(
                organization=self.organization,
                actor=self.actor,
                calculation=calculation,
                output_identifier="TAX-OUT-01",
            )
        schema = self._published_policy(
            PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
            self._schema_parameters("TEST-TAX-SCHEMA-V1"),
        )
        output = generate_statutory_output(
            organization=self.organization,
            actor=self.actor,
            calculation=calculation,
            output_identifier="TAX-OUT-01",
        )
        self.assertEqual(output.schema_version, schema)
        self.assertEqual(output.reconciliation.status, "matched")
        self.assertEqual(output.reconciliation.difference, 0)
        evidence = record_export_evidence(
            organization=self.organization,
            actor=self.actor,
            output=output,
            idempotency_key="tax-export-01",
            correlation_id="corr-tax-01",
            status=StatutoryExportStatus.EXPORTED,
            artifact_name="tax-output.json",
        )
        repeated = record_export_evidence(
            organization=self.organization,
            actor=self.actor,
            output=output,
            idempotency_key="tax-export-01",
            correlation_id="ignored-on-replay",
            status=StatutoryExportStatus.EXPORTED,
            artifact_name="tax-output.json",
        )
        self.assertEqual(repeated.pk, evidence.pk)
        self.assertEqual(output.export_evidence.count(), 1)
        self.assertEqual(evidence.artifact_snapshot["payload"], output.payload)
        replacement_run = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="STAT-RUN-REPLACEMENT",
            kind=PayrollRunKind.REPLACEMENT,
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="stat-run-replacement",
            replaces=self.run,
            predecessor=self.run,
            input_digest="replacement-input",
            calculation_digest="replacement-calculation",
            monetary_policy_snapshot=self.run.monetary_policy_snapshot,
            currency=self.run.currency,
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        replacement_employee = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=replacement_run,
            employee=self.employee,
            status=ResultStatus.FINALIZED,
            gross_amount=Decimal("1100.00"),
            net_amount=Decimal("1100.00"),
            predecessor_result=self.run_employee,
        )
        PayrollResultLine.objects.create(
            organization=self.organization,
            run=replacement_run,
            run_employee=replacement_employee,
            component=self.component,
            sequence=10,
            component_kind=ComponentKind.EARNING,
            basis=Decimal(1100),
            unrounded_amount=Decimal(1100),
            amount=Decimal("1100.00"),
            explanation={"fixture": "replacement"},
        )
        correction = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=replacement_run,
            kind=StatutoryCalculationKind.PAYROLL_TAX,
            record_kind=StatutoryRecordKind.CORRECTION,
            corrects=calculation,
            reason="Correction fixture",
        )
        review_statutory_calculation(
            organization=self.organization,
            actor=self.actor,
            calculation=correction,
            disposition=StatutoryReviewDisposition.ACCEPTED,
            reason="Correction reviewed",
        )
        correction_output = generate_statutory_output(
            organization=self.organization,
            actor=self.actor,
            calculation=correction,
            output_identifier="TAX-OUT-02",
            corrects=output,
        )
        self.assertEqual(correction.series_id, calculation.series_id)
        self.assertEqual(correction.revision, 2)
        self.assertEqual(correction_output.series_id, output.series_id)
        self.assertEqual(correction_output.revision, 2)
        with self.assertRaises(ValidationError):
            output.save()
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Obligation.objects.count(), 0)
        self.assertEqual(TreasuryMovement.objects.count(), 0)
        self.assertEqual(ProjectCostFact.objects.count(), 0)

    def test_permission_tenant_isolation_and_rtl_ui(self):
        self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        with self.assertRaises(PermissionDenied):
            calculate_statutory(
                organization=self.organization,
                actor=self.denied,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="Denied",
            )
        other_owner = User.objects.create_user(username="other-statutory-owner")
        other = create_organization_with_owner(
            owner=other_owner, name="Other Statutory", slug="other-statutory"
        )
        with self.assertRaises(PermissionDenied):
            calculate_statutory(
                organization=other,
                actor=self.actor,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="Cross tenant",
            )
        self.client.force_login(self.actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("payroll:statutory_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کارگاه مقرراتی مالیات و بیمه کارکنان")
        self.assertContains(response, "provider-neutral")
        self.assertContains(response, 'dir="rtl"')
        self.client.force_login(self.denied)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            self.client.get(reverse("payroll:statutory_workbench")).status_code,
            403,
        )

    def test_tenant_cannot_select_or_override_national_policy(self):
        policy_version = self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        self.assertFalse(policy_version.policy.tenant_selectable)
        self.assertFalse(
            self.organization.policy_selections.filter(
                policy=policy_version.policy
            ).exists()
        )
        with self.assertRaises(ValidationError):
            select_tenant_policy_version(
                organization=self.organization,
                actor=self.owner,
                policy_version=policy_version,
                reason="National policy cannot be selected",
            )


class StatutoryExportConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    _member = StatutoryPayrollTests._member
    _tax_parameters = StatutoryPayrollTests._tax_parameters
    _schema_parameters = StatutoryPayrollTests._schema_parameters
    _published_policy = StatutoryPayrollTests._published_policy

    def setUp(self) -> None:
        for permission in STATUTORY_PERMISSIONS:
            BusinessPermission.objects.update_or_create(
                code=permission.value,
                defaults={
                    "name": permission.label,
                    "description": permission.label,
                    "is_active": True,
                },
            )
        StatutoryPayrollTests.setUp(self)

    def test_concurrent_same_idempotency_key_records_one_export(self):
        self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        self._published_policy(
            PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
            self._schema_parameters("TEST-TAX-SCHEMA-CONCURRENT"),
        )
        calculation = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind=StatutoryCalculationKind.PAYROLL_TAX,
            reason="Concurrent fixture",
        )
        review_statutory_calculation(
            organization=self.organization,
            actor=self.actor,
            calculation=calculation,
            disposition=StatutoryReviewDisposition.ACCEPTED,
            reason="Concurrent review fixture",
        )
        output = generate_statutory_output(
            organization=self.organization,
            actor=self.actor,
            calculation=calculation,
            output_identifier="TAX-CONCURRENT-01",
        )

        def attempt(index: int):
            close_old_connections()
            try:
                evidence = record_export_evidence(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=self.actor.pk),
                    output=type(output).objects.get(pk=output.pk),
                    idempotency_key="concurrent-export-key",
                    correlation_id=f"concurrent-correlation-{index}",
                    status=StatutoryExportStatus.EXPORTED,
                    artifact_name="concurrent.json",
                )
                return evidence.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(attempt, (1, 2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(
            output.export_evidence.filter(
                idempotency_key="concurrent-export-key"
            ).count(),
            1,
        )
