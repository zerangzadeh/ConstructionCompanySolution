from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from hashlib import sha256
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.commercial_services import (
    commercial_exposure,
    create_compliance_evidence,
    create_compliance_evidence_revision,
    create_guarantee,
    create_guarantee_revision,
    create_retention_release,
    create_retention_release_correction,
    decide_compliance_evidence,
    decide_guarantee,
    decide_retention_release,
    expire_due_compliance_evidence,
    expire_due_guarantees,
    get_guarantees,
    submit_compliance_evidence,
    submit_guarantee,
    submit_retention_release,
)
from apps.billing.models import (
    AssuranceRevisionAction,
    ComplianceEvidenceKind,
    ComplianceEvidenceStatus,
    EvidenceExpiryKind,
    GuaranteeExposureSide,
    GuaranteeStatus,
    GuaranteeType,
    RetentionReleaseCorrectionKind,
    RetentionReleaseStatus,
)
from apps.billing.payable_services import (
    approve_payable_certificate,
    create_payable_certificate,
    create_payable_measurement,
    decide_payable_measurement,
    submit_payable_certificate,
    submit_payable_measurement,
)
from apps.contracts.models import (
    ContractDirection,
    ContractStatus,
    ContractType,
    RetentionReleaseRequirement,
)
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.documents.models import (
    Document,
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
    DocumentVersion,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import set_active_organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.projects.services import create_project
from apps.workflows.models import WorkflowInstanceStatus, WorkItemStatus


class CommercialControlFixture:
    def make_evidence(self, label: str) -> DocumentVersion:
        content = b"%PDF-1.4\ncommercial evidence"
        document = Document.objects.create(
            organization=self.organization,
            document_number=f"DOC-{label}",
            title=label,
            created_by=self.owner,
            updated_by=self.owner,
        )
        version = DocumentVersion.objects.create(
            organization=self.organization,
            document=document,
            version_number=1,
            original_file_name=f"{label}.pdf",
            file=SimpleUploadedFile(
                f"{label}.pdf", content, content_type="application/pdf"
            ),
            content_type="application/pdf",
            file_size=len(content),
            sha256=sha256(content).hexdigest(),
            uploaded_by=self.owner,
        )
        Document.objects.filter(pk=document.pk).update(current_version=version)
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=version,
            sequence=1,
            verdict=DocumentProcessingVerdict.CLEAN,
            input_sha256=version.sha256,
            adapter_code="test-scanner",
            recorded_by=self.owner,
        )
        return version

    def base_setup(self, *, slug: str, release_requirement: str) -> None:
        self.owner = User.objects.create_user(username=f"{slug}-owner")
        self.manager = User.objects.create_user(username=f"{slug}-manager")
        self.member = User.objects.create_user(username=f"{slug}-member")
        self.organization = Organization.objects.create(name=slug, slug=slug)
        self.organization.memberships.create(
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
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code=f"{slug[:5].upper()}-P",
            name="Commercial controls",
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Subcontractor",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number=f"{slug[:5].upper()}-C",
            title="Controlled subcontract",
            counterparty_name="Subcontractor",
            party=self.party,
            direction=ContractDirection.PAYABLE,
            contract_type=ContractType.SUBCONTRACT,
            contract_value=Decimal("1000.00"),
        )
        self.item = add_contract_item(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            description="Measured work",
            quantity=Decimal("10.0000"),
            unit_price=Decimal("100.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status=ContractStatus.ACTIVE,
        )
        self.contract.refresh_from_db()
        self.term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 1, 1),
            retention_rate=Decimal(10),
            retention_cap=Decimal(100),
            retention_release_requirement=release_requirement,
            retention_release_cap=(
                Decimal(100)
                if release_requirement != RetentionReleaseRequirement.UNCONFIGURED
                else Decimal(0)
            ),
            reason="Explicit contract terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=self.term,
            reason="Independent term approval",
        )

    def approve_retained_certificate(self) -> None:
        measurement = create_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            contract_item=self.item,
            measured_on=date(2026, 2, 15),
            period_quantity=Decimal("5.0000"),
            cumulative_quantity=Decimal("5.0000"),
            evidence_reference="SITE-MEASURE-1",
        )
        submit_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            measurement=measurement,
        )
        decide_payable_measurement(
            organization=self.organization,
            actor=self.manager,
            measurement=measurement,
            approved=True,
            reason="Verified",
        )
        certificate = create_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            measurement_cutoff=date(2026, 2, 28),
        )
        submit_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
        )
        approve_payable_certificate(
            organization=self.organization,
            actor=self.manager,
            certificate=certificate,
            reason="Independent certification",
        )


class CommercialControlTests(CommercialControlFixture, TestCase):
    def setUp(self) -> None:
        self.base_setup(
            slug="commercial-control",
            release_requirement=RetentionReleaseRequirement.EVIDENCE_ONLY,
        )
        self.evidence = self.make_evidence("guarantee-evidence")

    def _guarantee(self, *, expires_on: date = date(2027, 12, 31)):
        return create_guarantee(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            guarantee_type=GuaranteeType.PERFORMANCE,
            exposure_side=GuaranteeExposureSide.RECEIVED,
            instrument_reference="G-001",
            issuer_name="Evidence Bank",
            amount=Decimal("250.0000"),
            issued_on=date(2026, 10, 1),
            effective_from=date(2026, 10, 1),
            expiry_kind=EvidenceExpiryKind.DATED,
            expires_on=expires_on,
            evidence_document_version=self.evidence,
            reason="Contract-required performance guarantee",
        )

    def _approve_guarantee(self, guarantee):
        instance = submit_guarantee(
            organization=self.organization, actor=self.owner, guarantee=guarantee
        )
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        return decide_guarantee(
            organization=self.organization,
            actor=self.manager,
            guarantee=guarantee,
            approved=True,
            reason="Independent evidence review",
        )

    def test_guarantee_workflow_exposure_release_and_immutable_history(self) -> None:
        guarantee = self._guarantee()
        submit_guarantee(
            organization=self.organization, actor=self.owner, guarantee=guarantee
        )
        with self.assertRaises(PermissionDenied):
            decide_guarantee(
                organization=self.organization,
                actor=self.owner,
                guarantee=guarantee,
                approved=True,
                reason="Self approval",
            )
        guarantee = decide_guarantee(
            organization=self.organization,
            actor=self.manager,
            guarantee=guarantee,
            approved=True,
            reason="Independent review",
        )
        exposure = commercial_exposure(
            actor=self.owner, organization=self.organization, as_of=date(2026, 10, 3)
        )
        self.assertEqual(exposure["groups"][0]["amount"], Decimal("250.0000"))
        release_version = create_guarantee_revision(
            organization=self.organization,
            actor=self.owner,
            guarantee=guarantee,
            revision_action=AssuranceRevisionAction.RELEASE,
            evidence_document_version=self.make_evidence("guarantee-release"),
            reason="Contractual release evidence received",
        )
        submit_guarantee(
            organization=self.organization,
            actor=self.owner,
            guarantee=release_version,
        )
        decide_guarantee(
            organization=self.organization,
            actor=self.manager,
            guarantee=release_version,
            approved=True,
            reason="Release evidence accepted",
        )
        guarantee.refresh_from_db()
        release_version.refresh_from_db()
        self.assertEqual(guarantee.status, GuaranteeStatus.RELEASED)
        self.assertEqual(release_version.status, GuaranteeStatus.RELEASED)
        self.assertEqual(
            commercial_exposure(actor=self.owner, organization=self.organization)[
                "groups"
            ],
            [],
        )
        with self.assertRaises(ValidationError):
            guarantee.amount = Decimal("1.0000")
            guarantee.save()

    def test_expiry_and_compliance_renewal_preserve_history(self) -> None:
        guarantee = self._approve_guarantee(
            self._guarantee(expires_on=date(2026, 10, 10))
        )
        self.assertEqual(
            expire_due_guarantees(
                organization=self.organization,
                actor=self.owner,
                as_of=date(2026, 10, 11),
            ),
            1,
        )
        guarantee.refresh_from_db()
        self.assertEqual(guarantee.status, GuaranteeStatus.EXPIRED)
        clearance = create_compliance_evidence(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            evidence_kind=ComplianceEvidenceKind.CLEARANCE,
            reference="CLR-1",
            issuing_authority="Reviewed authority reference",
            effective_from=date(2026, 1, 1),
            expiry_kind=EvidenceExpiryKind.DATED,
            expires_on=date(2026, 10, 10),
            document_version=self.make_evidence("clearance-1"),
            reason="Contract evidence",
        )
        submit_compliance_evidence(
            organization=self.organization, actor=self.owner, evidence=clearance
        )
        clearance = decide_compliance_evidence(
            organization=self.organization,
            actor=self.manager,
            evidence=clearance,
            approved=True,
            reason="Evidence reviewed",
        )
        expire_due_compliance_evidence(
            organization=self.organization,
            actor=self.owner,
            as_of=date(2026, 10, 11),
        )
        clearance.refresh_from_db()
        self.assertEqual(clearance.status, ComplianceEvidenceStatus.EXPIRED)
        renewal = create_compliance_evidence_revision(
            organization=self.organization,
            actor=self.owner,
            evidence=clearance,
            revision_action=AssuranceRevisionAction.RENEWAL,
            reference="CLR-2",
            issuing_authority="Reviewed authority reference",
            effective_from=date(2026, 10, 11),
            expiry_kind=EvidenceExpiryKind.OPEN_ENDED,
            expires_on=None,
            document_version=self.make_evidence("clearance-2"),
            reason="Renewed evidence",
        )
        self.assertEqual(renewal.predecessor_id, clearance.pk)
        self.assertEqual(renewal.version, 2)

    def test_retention_release_calculation_correction_and_fail_closed_cap(self) -> None:
        self.approve_retained_certificate()
        release = create_retention_release(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            release_date=date(2026, 3, 1),
            amount=Decimal("30.0000"),
            evidence_document_version=self.make_evidence("release-1"),
        )
        self.assertEqual(release.retained_total_snapshot, Decimal("50.0000"))
        submit_retention_release(
            organization=self.organization, actor=self.owner, release=release
        )
        with self.assertRaises(PermissionDenied):
            decide_retention_release(
                organization=self.organization,
                actor=self.owner,
                release=release,
                approved=True,
                reason="Self approval",
            )
        release = decide_retention_release(
            organization=self.organization,
            actor=self.manager,
            release=release,
            approved=True,
            reason="Release authority checked",
        )
        with self.assertRaises(ValidationError):
            create_retention_release(
                organization=self.organization,
                actor=self.owner,
                contract=self.contract,
                release_date=date(2026, 3, 2),
                amount=Decimal("21.0000"),
                evidence_document_version=self.make_evidence("release-too-high"),
            )
        corrected = create_retention_release_correction(
            organization=self.organization,
            actor=self.owner,
            release=release,
            correction_kind=RetentionReleaseCorrectionKind.REPLACEMENT,
            amount=Decimal("20.0000"),
            evidence_document_version=self.make_evidence("release-correction"),
            reason="Correct authorized amount",
        )
        submit_retention_release(
            organization=self.organization, actor=self.owner, release=corrected
        )
        corrected = decide_retention_release(
            organization=self.organization,
            actor=self.manager,
            release=corrected,
            approved=True,
            reason="Correction reviewed",
        )
        release.refresh_from_db()
        self.assertEqual(release.status, RetentionReleaseStatus.SUPERSEDED)
        self.assertEqual(corrected.status, RetentionReleaseStatus.APPROVED)

    def test_clearance_requirement_is_explicit_and_effective_dated(self) -> None:
        self.approve_retained_certificate()
        later_term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 3, 10),
            retention_rate=Decimal(10),
            retention_cap=Decimal(100),
            retention_release_requirement=RetentionReleaseRequirement.APPROVED_CLEARANCE,
            retention_release_cap=Decimal(100),
            reason="Explicit clearance-gated release term",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=later_term,
            reason="Independent term approval",
        )
        with self.assertRaises(ValidationError):
            create_retention_release(
                organization=self.organization,
                actor=self.owner,
                contract=self.contract,
                release_date=date(2026, 3, 11),
                amount=Decimal("10.0000"),
                evidence_document_version=self.make_evidence("clearance-required"),
            )
        clearance = create_compliance_evidence(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            evidence_kind=ComplianceEvidenceKind.CLEARANCE,
            reference="CLR-RELEASE",
            issuing_authority="Reviewed authority reference",
            effective_from=date(2026, 3, 1),
            expiry_kind=EvidenceExpiryKind.OPEN_ENDED,
            expires_on=None,
            document_version=self.make_evidence("clearance-approved"),
            reason="Clearance evidence",
        )
        submit_compliance_evidence(
            organization=self.organization, actor=self.owner, evidence=clearance
        )
        clearance = decide_compliance_evidence(
            organization=self.organization,
            actor=self.manager,
            evidence=clearance,
            approved=True,
            reason="Clearance reviewed",
        )
        release = create_retention_release(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            release_date=date(2026, 3, 11),
            amount=Decimal("10.0000"),
            evidence_document_version=self.make_evidence("clearance-release"),
            clearance_evidence=clearance,
        )
        self.assertEqual(release.clearance_evidence_id, clearance.pk)
        self.assertEqual(
            release.contract_term_version.retention_release_requirement,
            RetentionReleaseRequirement.APPROVED_CLEARANCE,
        )

    def test_workflow_domain_and_audit_failure_roll_back_atomically(self) -> None:
        guarantee = self._guarantee()
        instance = submit_guarantee(
            organization=self.organization, actor=self.owner, guarantee=guarantee
        )
        with (
            patch(
                "apps.billing.commercial_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            decide_guarantee(
                organization=self.organization,
                actor=self.manager,
                guarantee=guarantee,
                approved=True,
                reason="Must roll back",
            )
        guarantee.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(guarantee.status, GuaranteeStatus.SUBMITTED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)

    def test_missing_contract_authority_unsafe_evidence_and_tenant_scope_fail_closed(
        self,
    ) -> None:
        with self.assertRaises(PermissionDenied):
            create_guarantee(
                organization=self.organization,
                actor=self.member,
                contract=self.contract,
                guarantee_type=GuaranteeType.BID,
                exposure_side=GuaranteeExposureSide.ISSUED,
                instrument_reference="NO-PERMISSION",
                issuer_name="Bank",
                amount=Decimal("1.0000"),
                issued_on=date(2026, 1, 1),
                effective_from=date(2026, 1, 1),
                expiry_kind=EvidenceExpiryKind.OPEN_ENDED,
                expires_on=None,
                evidence_document_version=self.evidence,
                reason="Must fail",
            )
        unconfigured = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="NO-RELEASE",
            title="No release authority",
            counterparty_name="Subcontractor",
            party=self.party,
            direction=ContractDirection.PAYABLE,
            contract_type=ContractType.SUBCONTRACT,
            contract_value=Decimal("10.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=unconfigured,
            status=ContractStatus.ACTIVE,
        )
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=unconfigured,
            effective_from=date(2026, 1, 1),
            reason="No release term",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Reviewed",
        )
        with self.assertRaises(ValidationError):
            create_retention_release(
                organization=self.organization,
                actor=self.owner,
                contract=unconfigured,
                release_date=date(2026, 3, 1),
                amount=Decimal("1.0000"),
                evidence_document_version=self.evidence,
            )
        unsafe_doc = Document.objects.create(
            organization=self.organization,
            document_number="DOC-UNSAFE",
            title="Unsafe",
            created_by=self.owner,
            updated_by=self.owner,
        )
        unsafe_version = DocumentVersion.objects.create(
            organization=self.organization,
            document=unsafe_doc,
            version_number=1,
            original_file_name="unsafe.pdf",
            file=SimpleUploadedFile("unsafe.pdf", b"%PDF-1.4"),
            content_type="application/pdf",
            file_size=8,
            sha256=sha256(b"%PDF-1.4").hexdigest(),
            uploaded_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            create_guarantee(
                organization=self.organization,
                actor=self.owner,
                contract=self.contract,
                guarantee_type=GuaranteeType.BID,
                exposure_side=GuaranteeExposureSide.ISSUED,
                instrument_reference="UNSAFE",
                issuer_name="Bank",
                amount=Decimal("1.0000"),
                issued_on=date(2026, 1, 1),
                effective_from=date(2026, 1, 1),
                expiry_kind=EvidenceExpiryKind.OPEN_ENDED,
                expires_on=None,
                evidence_document_version=unsafe_version,
                reason="Must fail",
            )
        other = Organization.objects.create(name="Other", slug="other-commercial")
        with self.assertRaises(PermissionDenied):
            get_guarantees(actor=self.owner, organization=other).count()

    def test_rtl_operational_dashboard_is_tenant_scoped(self) -> None:
        self._approve_guarantee(self._guarantee())
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("billing:commercial_control_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"', html=False)
        self.assertContains(response, "G-001")
        self.assertContains(response, "مواجهه فعال")
        self.assertNotContains(response, "تعهد پرداختنی")

    def test_audit_records_lifecycle_without_financial_side_effect(self) -> None:
        guarantee = self._approve_guarantee(self._guarantee())
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=guarantee.pk,
                action=AuditAction.GUARANTEE_APPROVED,
            ).exists()
        )
        self.assertFalse(hasattr(guarantee, "obligation"))


class RetentionReleaseConcurrencyTests(CommercialControlFixture, TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.base_setup(
            slug="release-race",
            release_requirement=RetentionReleaseRequirement.EVIDENCE_ONLY,
        )
        self.approve_retained_certificate()
        self.first = create_retention_release(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            release_date=date(2026, 3, 1),
            amount=Decimal("30.0000"),
            evidence_document_version=self.make_evidence("race-1"),
        )
        self.second = create_retention_release(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            release_date=date(2026, 3, 2),
            amount=Decimal("30.0000"),
            evidence_document_version=self.make_evidence("race-2"),
        )
        submit_retention_release(
            organization=self.organization, actor=self.owner, release=self.first
        )
        submit_retention_release(
            organization=self.organization, actor=self.owner, release=self.second
        )

    def test_concurrent_approval_cannot_over_release(self) -> None:
        barrier = Barrier(2)

        def approve(release_id) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                decide_retention_release(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.manager.pk),
                    release=self.first.__class__.objects.get(pk=release_id),
                    approved=True,
                    reason="Concurrent approval",
                )
                return "approved"
            except (ValidationError, PermissionDenied):
                return "blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(approve, [self.first.pk, self.second.pk]))
        self.assertEqual(results.count("approved"), 1)
        self.assertEqual(results.count("blocked"), 1)
        self.assertEqual(
            self.organization.retention_releases.filter(
                status=RetentionReleaseStatus.APPROVED
            ).count(),
            1,
        )
