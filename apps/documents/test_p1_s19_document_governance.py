from datetime import timedelta
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import DocumentConfidentiality, DocumentType
from apps.documents.services import (
    create_document,
    create_document_category,
    get_organization_document,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.projects.services import create_project


class P1S19DocumentGovernanceTests(TestCase):
    def setUp(self) -> None:
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            DOCUMENT_PROTECTED_ROOT=self.media_directory.name,
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(username="s19-owner", password="test")
        self.other_owner = User.objects.create_user(
            username="s19-other", password="test"
        )
        self.organization = Organization.objects.create(name="S19", slug="s19")
        self.other_organization = Organization.objects.create(
            name="S19 Other", slug="s19-other"
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-S19",
            name="S19 project",
        )

    @staticmethod
    def upload(name: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name, b"%PDF-1.7\ncontent", content_type="application/pdf"
        )

    def create_document(self, *, title: str, category=None):
        return create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title=title,
            upload=self.upload(f"{title}.pdf"),
            target=self.project,
            category=category,
            confidentiality=DocumentConfidentiality.CONFIDENTIAL,
        )

    def test_document_number_is_tenant_sequence_and_immutable(self) -> None:
        self.organization.settings.document_code_prefix = "FILE"
        self.organization.settings.save()

        first = self.create_document(title="First")
        second = self.create_document(title="Second")

        self.assertEqual(first.document_number, "FILE-000001")
        self.assertEqual(second.document_number, "FILE-000002")
        first.document_number = "FILE-999999"
        with self.assertRaises(ValidationError):
            first.save()

    def test_category_is_tenant_scoped_and_confidentiality_is_closed(self) -> None:
        category = create_document_category(
            organization=self.organization,
            actor=self.owner,
            code="contracts",
            name="Contract evidence",
        )
        document = self.create_document(title="Categorized", category=category)
        self.assertEqual(document.category, category)
        self.assertEqual(document.confidentiality, "confidential")

        other_category = create_document_category(
            organization=self.other_organization,
            actor=self.other_owner,
            code="other",
            name="Other Tenant",
        )
        with self.assertRaises(PermissionDenied):
            self.create_document(title="Cross tenant", category=other_category)

        with self.assertRaises(ValueError):
            create_document(
                organization=self.organization,
                actor=self.owner,
                document_type=DocumentType.GENERAL,
                title="Unknown confidentiality",
                upload=self.upload("unknown.pdf"),
                target=self.project,
                confidentiality="public",
            )

    def test_access_expiry_fails_closed(self) -> None:
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Expired",
            upload=self.upload("expired.pdf"),
            target=self.project,
            access_expires_at=timezone.now() - timedelta(seconds=1),
        )

        with self.assertRaises(PermissionDenied):
            get_organization_document(
                user=self.owner,
                organization=self.organization,
                document_id=str(document.pk),
            )
