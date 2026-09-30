from datetime import timedelta
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import (
    DisposalIntentState,
    DocumentProcessingVerdict,
    DocumentType,
    ManifestCompleteness,
    RecoveryEvidenceState,
    RetentionTrigger,
)
from apps.documents.services import (
    apply_document_retention_policy,
    approve_document_restore_evidence,
    approve_document_retention_policy_version,
    attest_document_key_custody,
    create_document,
    create_document_export_manifest,
    create_document_retention_policy,
    create_document_retention_policy_version,
    measure_document_storage,
    place_document_legal_hold,
    reconcile_document_recovery_boundary,
    record_document_processing_assessment,
    release_document_legal_hold,
    request_document_disposal,
    review_document_disposal_intent,
)
from apps.organizations.access_services import assign_platform_role
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
    PlatformRoleCode,
)
from apps.projects.services import create_project


class P1S22RetentionRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)

        self.owner = User.objects.create_user(username="s22-owner")
        self.approver = User.objects.create_user(username="s22-approver")
        self.organization = Organization.objects.create(name="S22", slug="s22")
        OrganizationSettings.objects.create(organization=self.organization)
        for user in (self.owner, self.approver):
            self.organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.ACTIVE,
            )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-S22",
            name="S22 project",
        )
        self.document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Retention evidence",
            upload=SimpleUploadedFile(
                "retention.pdf",
                b"%PDF-1.7\nretention evidence",
                content_type="application/pdf",
            ),
            target=self.project,
        )

        assigner = User.objects.create_superuser(username="s22-assigner")
        role_approver = User.objects.create_superuser(username="s22-role-approver")
        self.operator = User.objects.create_user(username="s22-operator")
        self.security = User.objects.create_user(username="s22-security")
        self.restore_approver = User.objects.create_user(username="s22-restore")
        for target, role in (
            (self.operator, PlatformRoleCode.PLATFORM_OPERATIONS),
            (self.security, PlatformRoleCode.PLATFORM_SECURITY),
            (
                self.restore_approver,
                PlatformRoleCode.RESTORE_EVIDENCE_APPROVER,
            ),
        ):
            assign_platform_role(
                actor=assigner,
                approver=role_approver,
                target=target,
                role=role,
                reason="S22 separated platform duty",
            )

    def test_unknown_duration_and_separated_hold_disposal_fail_closed(self) -> None:
        policy = create_document_retention_policy(
            organization=self.organization,
            actor=self.owner,
            code="legal-evidence",
            name="Legal evidence",
        )
        version = create_document_retention_policy_version(
            policy=policy,
            actor=self.owner,
            trigger=RetentionTrigger.DOCUMENT_RECEIVED,
            duration_days=None,
            source_reference="Tenant-approved source pending duration",
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        approved = approve_document_retention_policy_version(
            version=version, actor=self.owner
        )
        application = apply_document_retention_policy(
            document=self.document,
            policy_version=approved,
            actor=self.owner,
        )
        self.assertIsNone(application.retention_until)

        hold = place_document_legal_hold(
            document=self.document,
            actor=self.owner,
            reason="Active dispute",
            source_reference="CASE-REF",
        )
        with self.assertRaises(PermissionDenied):
            release_document_legal_hold(
                hold=hold,
                actor=self.owner,
                reason="self release denied",
            )
        release_document_legal_hold(
            hold=hold,
            actor=self.approver,
            reason="independent release",
        )

        intent = request_document_disposal(
            document=self.document,
            actor=self.owner,
            reason="eligibility review only",
        )
        with self.assertRaises(PermissionDenied):
            review_document_disposal_intent(intent=intent, actor=self.owner)
        reviewed = review_document_disposal_intent(
            intent=intent, actor=self.approver
        )
        self.assertEqual(reviewed.state, DisposalIntentState.BLOCKED)
        self.assertIn("نامشخص", reviewed.block_reason)
        self.assertTrue(self.document.versions.filter(pk=self.document.current_version_id).exists())

    def test_export_accounting_and_recovery_roles_share_one_boundary(self) -> None:
        record_document_processing_assessment(
            version=self.document.current_version,
            actor=self.operator,
            verdict=DocumentProcessingVerdict.CLEAN,
            adapter_code="s22-test-scanner",
        )
        export = create_document_export_manifest(
            organization=self.organization,
            actor=self.owner,
            document_ids=[self.document.pk],
        )
        self.assertEqual(export.completeness, ManifestCompleteness.COMPLETE)
        byte_counts = measure_document_storage(organization=self.organization)
        self.assertEqual(
            byte_counts["original_bytes"], self.document.current_version.file_size
        )
        self.assertEqual(byte_counts["quarantine_bytes"], 0)
        self.assertEqual(byte_counts["derivative_bytes"], 0)

        with self.assertRaises(PermissionDenied):
            attest_document_key_custody(
                organization=self.organization,
                actor=self.operator,
                reference="wrong duty",
            )
        attestation = attest_document_key_custody(
            organization=self.organization,
            actor=self.security,
            reference="test key-custody evidence",
        )
        manifest = reconcile_document_recovery_boundary(
            organization=self.organization,
            actor=self.operator,
            database_reference="test database snapshot evidence",
            key_custody_attestation=attestation,
        )
        self.assertEqual(manifest.boundary_id, attestation.boundary_id)
        self.assertEqual(manifest.state, RecoveryEvidenceState.RECONCILED)
        approved = approve_document_restore_evidence(
            manifest=manifest,
            actor=self.restore_approver,
        )
        self.assertEqual(approved.state, RecoveryEvidenceState.APPROVED)
