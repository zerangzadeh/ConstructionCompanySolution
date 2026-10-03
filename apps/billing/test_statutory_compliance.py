from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.billing.models import (
    ClaimAdjustment,
    ClaimAdjustmentType,
    ContractorComplianceAssessment,
    PayableCertificate,
    PayableCertificateStatus,
    ProgressClaim,
    ProjectBaseline,
    ProjectBaselineStatus,
    StatutoryRecordKind,
    StatutoryRecordStatus,
    StatutorySubmissionEvidence,
    StatutorySubmissionStatus,
    SubmissionResolutionAction,
    TaxpayerInvoice,
)
from apps.billing.statutory_services import (
    AdapterResult,
    create_contractor_compliance_assessment,
    create_taxpayer_invoice,
    decide_contractor_assessment,
    decide_taxpayer_invoice,
    reconcile_contractor_assessment,
    reconcile_taxpayer_invoice,
    record_statutory_submission,
    resolve_submission_error,
    submit_contractor_assessment,
    submit_taxpayer_invoice,
)
from apps.contracts.models import ContractDirection, ContractStatus, ContractType
from apps.contracts.services import (
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformPolicy,
    PlatformPolicyVersion,
    PlatformPolicyVersionSource,
    PolicyReviewDisposition,
    PolicyReviewEvidence,
    PolicySource,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
    RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
    TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
    get_platform_policy_spec,
)
from apps.organizations.services import set_active_organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.projects.services import create_project
from apps.subledgers.models import Obligation


class AcceptingAdapter:
    def submit(self, *, payload, correlation_id, schema_identifier):
        return AdapterResult(
            status=StatutorySubmissionStatus.ACCEPTED,
            response_payload={"echo": payload, "schema": schema_identifier},
            provider_reference=f"TEST-{correlation_id}",
        )


class OutageAdapter:
    def submit(self, **_):
        raise TimeoutError("test outage")


class StatutoryComplianceFixture:
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="stat-owner")
        self.manager = User.objects.create_user(username="stat-manager")
        self.viewer = User.objects.create_user(username="stat-viewer")
        self.organization = Organization.objects.create(name="Stat", slug="stat")
        self.owner_membership = self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.manager_membership = self.organization.memberships.create(
            user=self.manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="STAT-P",
            name="Statutory project",
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Counterparty",
            tax_identifier="TEST-TAX-ID",
        )
        self.receivable_contract, self.receivable_term = self._contract(
            direction=ContractDirection.RECEIVABLE,
            number="RCV-1",
            contract_type=ContractType.CLIENT,
        )
        self.payable_contract, self.payable_term = self._contract(
            direction=ContractDirection.PAYABLE,
            number="PAY-1",
            contract_type=ContractType.SUBCONTRACT,
        )
        self.claim_policy = self._policy(
            code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
            version=1,
            parameters={
                "tax_rate": "10",
                "tax_basis": "gross",
                "insurance_rate": "0",
                "insurance_basis": "gross",
            },
            select=False,
        )
        self.invoice_policy = self._policy(
            code=TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
            version=1,
            parameters={
                "schema_identifier": "TEST-SCHEMA-V1",
                "submission_mode": "test_adapter",
                "provider_key": "deterministic-test",
                "tax_code": "TEST-VAT",
                "field_mapping": {
                    "invoiceId": "taxpayer_invoice_id",
                    "kind": "document_kind",
                    "partyTaxId": "party_tax_identifier",
                    "taxCode": "tax_code",
                    "taxable": "taxable_amount",
                    "tax": "tax_amount",
                    "total": "total_amount",
                },
                "required_fields": [
                    "invoiceId",
                    "kind",
                    "partyTaxId",
                    "taxCode",
                    "taxable",
                    "tax",
                    "total",
                ],
            },
        )
        self.contractor_policy = self._policy(
            code=CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
            version=1,
            parameters={
                "deduction_rate": "5",
                "deduction_basis": "gross",
                "clearance_required": False,
                "schema_identifier": "TEST-CONTRACTOR-V1",
            },
        )
        self.claim = self._claim()
        self.certificate = self._certificate()

    def _contract(self, *, direction, number, contract_type):
        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number=number,
            title=number,
            counterparty_name=self.party.display_name,
            party=self.party,
            direction=direction,
            contract_type=contract_type,
            contract_value=Decimal("1000.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=contract,
            status=ContractStatus.ACTIVE,
        )
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=contract,
            effective_from=date(2026, 1, 1),
            reason="Test commercial authority",
        )
        term = approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent test approval",
        )
        return contract, term

    def _policy(
        self,
        *,
        code,
        version,
        parameters,
        select=True,
        effective_from=date(2026, 1, 1),
        effective_to=None,
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
        source = PolicySource.objects.create(
            issuer="Test external authority",
            title=f"Reviewed source {code} v{version}",
            source_identifier=f"{code}-{version}-{uuid4()}",
            version=str(version),
            effective_from=effective_from,
            applicability="Test-only statutory fixture",
            reason="Verified test provenance",
            created_by=self.owner,
        )
        policy_version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=version,
            parameters=parameters,
            effective_from=effective_from,
            effective_to=effective_to,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            reason="Reviewed test rule",
            created_by=self.owner,
        )
        PlatformPolicyVersionSource.objects.create(
            policy_version=policy_version,
            source=source,
            linked_by=self.owner,
            reason="Test provenance link",
        )
        PolicyReviewEvidence.objects.create(
            policy_version=policy_version,
            reviewer_identity="Independent test reviewer",
            qualification_summary="Test fixture only",
            independence_statement="Independent from preparer",
            evidence_reference=f"REVIEW-{code}-{version}",
            reviewed_on=date(2026, 1, 1),
            review_scope="Test policy shape and values",
            disposition=PolicyReviewDisposition.ACCEPTED,
            created_by=self.manager,
        )
        PlatformPolicyVersion.objects.filter(pk=policy_version.pk).update(
            status=PolicyVersionStatus.PUBLISHED,
            published_by=self.manager,
            published_at=timezone.now(),
        )
        policy_version.refresh_from_db()
        if select and policy.tenant_selectable:
            TenantPolicySelection.objects.create(
                organization=self.organization,
                policy=policy,
                policy_version=policy_version,
                status=TenantPolicySelectionStatus.ACTIVE,
                approved_by=self.manager_membership,
                approved_at=timezone.now(),
                applied_by=self.manager_membership,
                applied_at=timezone.now(),
                reason="Test tenant selection",
            )
        return policy_version

    def _claim(
        self,
        *,
        number=1,
        correction_kind="ordinary",
        corrects=None,
        approved_on=date(2026, 2, 1),
    ):
        baseline = ProjectBaseline.objects.filter(
            organization=self.organization,
            contract=self.receivable_contract,
            status=ProjectBaselineStatus.APPROVED,
        ).first()
        if baseline is None:
            baseline = ProjectBaseline.objects.create(
                organization=self.organization,
                project=self.project,
                contract=self.receivable_contract,
                version=number,
                effective_date=date(2026, 1, 1),
                contract_value_snapshot=Decimal("1000.00"),
                effective_ceiling=Decimal("1000.00"),
                status=ProjectBaselineStatus.APPROVED,
                approved_by=self.manager,
                approved_at=timezone.now(),
                approval_reason="Test baseline",
                created_by=self.owner,
                updated_by=self.owner,
            )
        is_cancellation = correction_kind == "cancellation"
        claim = ProgressClaim.objects.create(
            organization=self.organization,
            project=self.project,
            contract=self.receivable_contract,
            baseline=baseline,
            claim_number=number if corrects is None else corrects.claim_number,
            revision_number=1 if corrects is None else corrects.revision_number + 1,
            correction_kind=correction_kind,
            corrects=corrects,
            correction_reason="" if corrects is None else "Linked correction",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            measurement_cutoff=date(2026, 1, 31),
            billing_configuration_snapshot={"test": True},
            calculation_snapshot={"test": True},
            contract_term_version=self.receivable_term,
            regulatory_rule_version=self.claim_policy,
            party_identity_snapshot=self.party.identity_snapshots.get(sequence=1),
            currency_code="IRR",
            due_date=date(2026, 2, 15),
            gross_amount=Decimal(0) if is_cancellation else Decimal("100.0000"),
            adjustment_amount=(Decimal(0) if is_cancellation else Decimal("10.0000")),
            net_amount=Decimal(0) if is_cancellation else Decimal("110.0000"),
            created_by=self.owner,
            updated_by=self.owner,
        )
        if not is_cancellation:
            ClaimAdjustment.objects.create(
                claim=claim,
                adjustment_type=ClaimAdjustmentType.TAX,
                description="Reviewed test tax",
                sequence=1,
                rate_snapshot=Decimal(10),
                base_amount_snapshot=Decimal("100.0000"),
                amount=Decimal("10.0000"),
            )
        if corrects is not None:
            ProgressClaim.objects.filter(pk=corrects.pk).update(
                status=(
                    "cancelled" if correction_kind == "cancellation" else "superseded"
                )
            )
        ProgressClaim.objects.filter(pk=claim.pk).update(
            status="approved",
            approved_by=self.manager,
            approved_at=timezone.make_aware(
                timezone.datetime(
                    approved_on.year, approved_on.month, approved_on.day, 9
                )
            ),
            approval_reason="Independent approval",
        )
        claim.refresh_from_db()
        return claim

    def _certificate(self):
        return PayableCertificate.objects.create(
            organization=self.organization,
            project=self.project,
            contract=self.payable_contract,
            contract_term_version=self.payable_term,
            party_identity_snapshot=self.party.identity_snapshots.get(sequence=1),
            certificate_number=1,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            measurement_cutoff=date(2026, 1, 31),
            currency_code="IRR",
            due_date=date(2026, 2, 15),
            gross_amount=Decimal("200.0000"),
            net_amount=Decimal("180.0000"),
            calculation_snapshot={"test": True},
            status=PayableCertificateStatus.APPROVED,
            approved_by=self.manager,
            approved_at=timezone.now(),
            approval_reason="Independent approval",
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _approved_invoice(self):
        invoice = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=self.claim,
            record_kind=StatutoryRecordKind.ORIGINAL,
            reason="Test original",
        )
        submit_taxpayer_invoice(
            organization=self.organization, actor=self.owner, invoice=invoice
        )
        return decide_taxpayer_invoice(
            organization=self.organization,
            actor=self.manager,
            invoice=invoice,
            approved=True,
            reason="Independent statutory approval",
        )


class StatutoryComplianceTests(StatutoryComplianceFixture, TestCase):
    def test_reviewed_policy_preflight_and_tax_code_are_pinned(self) -> None:
        invoice = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=self.claim,
            record_kind=StatutoryRecordKind.ORIGINAL,
            reason="Initial statutory derivative",
        )
        self.assertEqual(invoice.tax_code, "TEST-VAT")
        self.assertEqual(invoice.taxable_amount, Decimal("100.0000"))
        self.assertEqual(invoice.tax_amount, Decimal("10.0000"))
        self.assertTrue(invoice.preflight_snapshot["passed"])
        self.assertEqual(invoice.payload_snapshot["partyTaxId"], "TEST-TAX-ID")

    def test_missing_platform_regulatory_policy_fails_closed(self) -> None:
        PlatformPolicy.objects.filter(
            code=TAXPAYER_INVOICE_REGULATORY_POLICY_CODE
        ).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, "نسخه مقرراتی پلتفرم"):
            create_taxpayer_invoice(
                organization=self.organization,
                actor=self.owner,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Must fail",
            )

    def test_unreviewed_regulatory_policy_fails_closed(self) -> None:
        PolicyReviewEvidence.objects.filter(policy_version=self.invoice_policy).delete()
        with self.assertRaisesMessage(ValidationError, "فاقد منبع"):
            create_taxpayer_invoice(
                organization=self.organization,
                actor=self.owner,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Unreviewed policy denied",
            )

    def test_prepare_permission_is_denied_by_default(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_taxpayer_invoice(
                organization=self.organization,
                actor=self.viewer,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Viewer denied",
            )

    def test_persian_operational_dashboard_is_tenant_scoped(self) -> None:
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("billing:statutory_operations_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "صورتحساب مؤدیان و عملیات مقرراتی")
        self.assertContains(response, "هیچ اثر خودکار")

    def test_schema_preflight_rejects_missing_mapped_authority(self) -> None:
        snapshot = self.party.identity_snapshots.get(sequence=1)
        type(snapshot).objects.filter(pk=snapshot.pk).update(tax_identifier="")
        self.claim.party_identity_snapshot.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "preflight"):
            create_taxpayer_invoice(
                organization=self.organization,
                actor=self.owner,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Missing statutory identifier",
            )

    def test_effective_policy_rollover_selects_source_date_version(self) -> None:
        parameters = self.invoice_policy.parameters.copy()
        parameters["schema_identifier"] = "TEST-SCHEMA-V2"
        parameters["tax_code"] = "TEST-VAT-V2"
        second = self._policy(
            code=TAXPAYER_INVOICE_REGULATORY_POLICY_CODE,
            version=2,
            parameters=parameters,
            effective_from=date(2026, 3, 1),
        )
        old_invoice = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=self.claim,
            record_kind=StatutoryRecordKind.ORIGINAL,
            reason="Before rollover",
        )
        later_claim = self._claim(number=2, approved_on=date(2026, 3, 15))
        new_invoice = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=later_claim,
            record_kind=StatutoryRecordKind.ORIGINAL,
            reason="After rollover",
        )
        self.assertEqual(old_invoice.policy_version_id, self.invoice_policy.pk)
        self.assertEqual(new_invoice.policy_version_id, second.pk)
        self.assertEqual(new_invoice.tax_code, "TEST-VAT-V2")

    def test_workflow_sod_and_immutable_approval(self) -> None:
        invoice = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=self.claim,
            record_kind=StatutoryRecordKind.ORIGINAL,
            reason="Workflow",
        )
        submit_taxpayer_invoice(
            organization=self.organization, actor=self.owner, invoice=invoice
        )
        with self.assertRaises(PermissionDenied):
            decide_taxpayer_invoice(
                organization=self.organization,
                actor=self.owner,
                invoice=invoice,
                approved=True,
                reason="Self approval denied",
            )
        invoice = decide_taxpayer_invoice(
            organization=self.organization,
            actor=self.manager,
            invoice=invoice,
            approved=True,
            reason="Independent approval",
        )
        invoice.tax_code = "MUTATED"
        with self.assertRaises(ValidationError):
            invoice.save()

    def test_linked_correction_and_cancellation_lineage(self) -> None:
        original = self._approved_invoice()
        correction_claim = self._claim(
            correction_kind="replacement", corrects=self.claim
        )
        correction = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=correction_claim,
            record_kind=StatutoryRecordKind.CORRECTION,
            corrects=original,
            reason="Commercial correction lineage",
        )
        submit_taxpayer_invoice(
            organization=self.organization, actor=self.owner, invoice=correction
        )
        correction = decide_taxpayer_invoice(
            organization=self.organization,
            actor=self.manager,
            invoice=correction,
            approved=True,
            reason="Correction approved",
        )
        original.refresh_from_db()
        self.assertEqual(original.status, StatutoryRecordStatus.SUPERSEDED)
        self.assertEqual(correction.series_id, original.series_id)
        cancellation_claim = self._claim(
            correction_kind="cancellation", corrects=correction_claim
        )
        cancellation = create_taxpayer_invoice(
            organization=self.organization,
            actor=self.owner,
            source_claim=cancellation_claim,
            record_kind=StatutoryRecordKind.CANCELLATION,
            corrects=correction,
            reason="Commercial cancellation lineage",
        )
        submit_taxpayer_invoice(
            organization=self.organization, actor=self.owner, invoice=cancellation
        )
        cancellation = decide_taxpayer_invoice(
            organization=self.organization,
            actor=self.manager,
            invoice=cancellation,
            approved=True,
            reason="Cancellation approved",
        )
        correction.refresh_from_db()
        self.assertEqual(correction.status, StatutoryRecordStatus.CANCELLED)
        self.assertEqual(cancellation.total_amount, 0)

    def test_idempotent_submission_outage_resolution_and_retry(self) -> None:
        invoice = self._approved_invoice()
        first = record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=invoice,
            idempotency_key="attempt-1",
            correlation_id=uuid4(),
            adapter=OutageAdapter(),
        )
        self.assertEqual(first.status, StatutorySubmissionStatus.PROVIDER_ERROR)
        same = record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=invoice,
            idempotency_key="attempt-1",
            correlation_id=uuid4(),
            adapter=AcceptingAdapter(),
        )
        self.assertEqual(same.pk, first.pk)
        with self.assertRaises(PermissionDenied):
            record_statutory_submission(
                organization=self.organization,
                actor=self.viewer,
                target=invoice,
                idempotency_key="attempt-1",
                correlation_id=uuid4(),
                adapter=AcceptingAdapter(),
            )
        resolve_submission_error(
            organization=self.organization,
            actor=self.manager,
            submission=first,
            action=SubmissionResolutionAction.RETRY_AUTHORIZED,
            note="Reviewed outage; retry allowed",
        )
        retry = record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=invoice,
            idempotency_key="attempt-2",
            correlation_id=uuid4(),
            adapter=AcceptingAdapter(),
            retry_of=first,
        )
        self.assertEqual(retry.status, StatutorySubmissionStatus.ACCEPTED)
        self.assertEqual(retry.attempt_number, 2)
        self.assertEqual(retry.retry_of, first)
        with self.assertRaisesMessage(ValidationError, "قبلاً"):
            record_statutory_submission(
                organization=self.organization,
                actor=self.owner,
                target=invoice,
                idempotency_key="attempt-3",
                correlation_id=uuid4(),
                adapter=AcceptingAdapter(),
            )

    def test_credentials_are_rejected_from_adapter_evidence(self) -> None:
        class UnsafeAdapter:
            def submit(self, **_):
                return AdapterResult(
                    status=StatutorySubmissionStatus.ACCEPTED,
                    response_payload={"access_token": "must-not-persist"},
                )

        invoice = self._approved_invoice()
        with self.assertRaisesMessage(ValidationError, "credential"):
            record_statutory_submission(
                organization=self.organization,
                actor=self.owner,
                target=invoice,
                idempotency_key="unsafe",
                correlation_id=uuid4(),
                adapter=UnsafeAdapter(),
            )
        self.assertFalse(
            StatutorySubmissionEvidence.objects.filter(
                organization=self.organization, idempotency_key="unsafe"
            ).exists()
        )

    def test_contractor_deduction_is_evidence_only(self) -> None:
        obligations_before = Obligation.objects.count()
        journals_before = JournalEntry.objects.count()
        certificate_snapshot = (
            self.certificate.status,
            self.certificate.gross_amount,
            self.certificate.net_amount,
        )
        assessment = create_contractor_compliance_assessment(
            organization=self.organization,
            actor=self.owner,
            source_certificate=self.certificate,
        )
        self.assertEqual(assessment.basis_amount, Decimal("200.0000"))
        self.assertEqual(assessment.deduction_amount, Decimal("10.0000"))
        submit_contractor_assessment(
            organization=self.organization,
            actor=self.owner,
            assessment=assessment,
        )
        assessment = decide_contractor_assessment(
            organization=self.organization,
            actor=self.manager,
            assessment=assessment,
            approved=True,
            reason="Independent compliance approval",
        )
        evidence = record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=assessment,
            idempotency_key="contractor-reconciliation",
            correlation_id=uuid4(),
        )
        reconciliation = reconcile_contractor_assessment(
            actor=self.owner,
            organization=self.organization,
            assessment=assessment,
        )
        self.certificate.refresh_from_db()
        self.assertEqual(
            certificate_snapshot,
            (
                self.certificate.status,
                self.certificate.gross_amount,
                self.certificate.net_amount,
            ),
        )
        self.assertEqual(Obligation.objects.count(), obligations_before)
        self.assertEqual(JournalEntry.objects.count(), journals_before)
        self.assertEqual(reconciliation["financial_effect"], "none")
        self.assertEqual(
            reconciliation["submission_evidence"][0]["correlation_id"],
            str(evidence.correlation_id),
        )
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "billing:contractor_compliance_detail",
                kwargs={"assessment_id": assessment.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(evidence.correlation_id))

    def test_reviewed_clearance_requirement_fails_closed_when_missing(self) -> None:
        self._policy(
            code=CONTRACTOR_COMPLIANCE_REGULATORY_POLICY_CODE,
            version=2,
            effective_from=date(2026, 10, 1),
            parameters={
                "deduction_rate": "5",
                "deduction_basis": "gross",
                "clearance_required": True,
                "schema_identifier": "TEST-CONTRACTOR-V2",
            },
        )
        with self.assertRaisesMessage(ValidationError, "مفاصاحساب معتبر"):
            create_contractor_compliance_assessment(
                organization=self.organization,
                actor=self.owner,
                source_certificate=self.certificate,
            )

    def test_cross_tenant_target_is_denied(self) -> None:
        other = Organization.objects.create(name="Other", slug="other-stat")
        other.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            create_taxpayer_invoice(
                organization=other,
                actor=self.owner,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Cross tenant",
            )

    def test_audit_failure_rolls_back_invoice(self) -> None:
        with (
            patch(
                "apps.billing.statutory_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            create_taxpayer_invoice(
                organization=self.organization,
                actor=self.owner,
                source_claim=self.claim,
                record_kind=StatutoryRecordKind.ORIGINAL,
                reason="Atomic audit",
            )
        self.assertFalse(TaxpayerInvoice.objects.exists())

    def test_reconciliation_preserves_source_and_correlation(self) -> None:
        invoice = self._approved_invoice()
        claim_before = (self.claim.status, self.claim.net_amount)
        evidence = record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=invoice,
            idempotency_key="reconcile",
            correlation_id=uuid4(),
            adapter=AcceptingAdapter(),
        )
        result = reconcile_taxpayer_invoice(
            actor=self.owner,
            organization=self.organization,
            invoice=invoice,
        )
        self.claim.refresh_from_db()
        self.assertEqual(claim_before, (self.claim.status, self.claim.net_amount))
        self.assertEqual(result["financial_effect"], "none")
        self.assertEqual(
            result["submission_evidence"][0]["correlation_id"],
            str(evidence.correlation_id),
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="statutory_submission.recorded",
                correlation_id=evidence.correlation_id,
            ).exists()
        )

    def test_duplicate_assessment_source_is_prevented(self) -> None:
        create_contractor_compliance_assessment(
            organization=self.organization,
            actor=self.owner,
            source_certificate=self.certificate,
        )
        with self.assertRaises(ValidationError):
            create_contractor_compliance_assessment(
                organization=self.organization,
                actor=self.owner,
                source_certificate=self.certificate,
            )
        self.assertEqual(ContractorComplianceAssessment.objects.count(), 1)


class StatutorySubmissionConcurrencyTests(
    StatutoryComplianceFixture, TransactionTestCase
):
    reset_sequences = True

    def test_concurrent_same_idempotency_key_returns_one_attempt(self) -> None:
        invoice = self._approved_invoice()
        correlation_id = uuid4()

        def submit_once():
            close_old_connections()
            try:
                result = record_statutory_submission(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    target=TaxpayerInvoice.objects.get(pk=invoice.pk),
                    idempotency_key="concurrent-attempt",
                    correlation_id=correlation_id,
                    adapter=AcceptingAdapter(),
                )
                return result.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: submit_once(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(
            StatutorySubmissionEvidence.objects.filter(
                organization=self.organization,
                idempotency_key="concurrent-attempt",
            ).count(),
            1,
        )
