from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.documents.models import (
    DocumentProcessingVerdict,
    DocumentType,
    SignatureVerificationState,
)
from apps.documents.services import (
    add_document_version,
    compare_document_versions,
    create_document,
    get_document_version_for_download,
    get_organization_documents,
    record_document_processing_assessment,
    record_document_signature_evidence,
    search_organization_documents,
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


class P1S21DocumentProcessingTests(TestCase):
    def setUp(self) -> None:
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)

        self.owner = User.objects.create_user(username="s21-owner")
        self.organization = Organization.objects.create(name="S21", slug="s21")
        OrganizationSettings.objects.create(organization=self.organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-S21",
            name="S21 project",
        )
        assigner = User.objects.create_superuser(username="s21-assigner")
        approver = User.objects.create_superuser(username="s21-approver")
        self.operator = User.objects.create_user(username="s21-operator")
        assign_platform_role(
            actor=assigner,
            approver=approver,
            target=self.operator,
            role=PlatformRoleCode.PLATFORM_OPERATIONS,
            reason="S21 processing duty",
        )

    @staticmethod
    def upload(name: str, suffix: bytes = b"") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name,
            b"%PDF-1.7\ncontent" + suffix,
            content_type="application/pdf",
        )

    def create_document(self):
        return create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Processing evidence",
            upload=self.upload("processing.pdf"),
            target=self.project,
        )

    def test_unknown_and_latest_non_clean_assessment_fail_closed(self) -> None:
        document = self.create_document()
        version = document.current_version

        with self.assertRaises(PermissionDenied):
            get_document_version_for_download(
                document=document,
                version_id=version.pk,
                actor=self.owner,
            )
        with self.assertRaises(ValueError):
            version.file.storage.url(version.file.name)
        with self.assertRaises(PermissionDenied):
            record_document_processing_assessment(
                version=version,
                actor=self.owner,
                verdict=DocumentProcessingVerdict.CLEAN,
                adapter_code="forged",
            )

        clean = record_document_processing_assessment(
            version=version,
            actor=self.operator,
            verdict=DocumentProcessingVerdict.CLEAN,
            adapter_code="scanner-adapter",
            extracted_text="foundation excavation evidence",
        )
        self.assertTrue(version.is_available)
        with self.assertRaises(ValidationError):
            clean.delete()

        record_document_processing_assessment(
            version=version,
            actor=self.operator,
            verdict=DocumentProcessingVerdict.ERROR,
            adapter_code="scanner-adapter",
            details={"reason": "provider unavailable"},
        )
        self.assertFalse(version.is_available)
        with self.assertRaises(PermissionDenied):
            get_document_version_for_download(
                document=document,
                version_id=version.pk,
                actor=self.owner,
            )
        self.assertFalse(
            search_organization_documents(
                user=self.owner,
                organization=self.organization,
                query="excavation",
            ).exists()
        )

    def test_permission_scoped_search_compare_and_signature_boundary(self) -> None:
        document = self.create_document()
        first = document.current_version
        record_document_processing_assessment(
            version=first,
            actor=self.operator,
            verdict=DocumentProcessingVerdict.CLEAN,
            adapter_code="scanner-adapter",
            extracted_text="reinforcement inspection",
        )
        second = add_document_version(
            document=document,
            actor=self.owner,
            upload=self.upload("processing-v2.pdf", b"-v2"),
        )
        record_document_processing_assessment(
            version=second,
            actor=self.operator,
            verdict=DocumentProcessingVerdict.CLEAN,
            adapter_code="scanner-adapter",
            extracted_text="reinforcement inspection revised",
        )

        self.assertTrue(
            get_organization_documents(
                user=self.owner, organization=self.organization
            ).filter(pk=document.pk).exists()
        )
        self.assertEqual(
            list(
                search_organization_documents(
                    user=self.owner,
                    organization=self.organization,
                    query="reinforcement",
                ).values_list("pk", flat=True)
            ),
            [document.pk],
        )
        comparison = compare_document_versions(
            document=document,
            actor=self.owner,
            left_version_id=first.pk,
            right_version_id=second.pk,
        )
        self.assertNotEqual(
            comparison["left"]["sha256"], comparison["right"]["sha256"]
        )
        signature = record_document_signature_evidence(
            version=second,
            actor=self.operator,
        )
        self.assertEqual(
            signature.verification_state, SignatureVerificationState.UNKNOWN
        )
        self.assertEqual(signature.standard_code, "")
