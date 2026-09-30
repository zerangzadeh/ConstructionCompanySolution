import hashlib
from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.forms import DocumentCreateForm
from apps.documents.models import DocumentLink, DocumentType
from apps.documents.services import (
    add_document_link,
    add_document_version,
    archive_document,
    create_document,
    get_organization_document,
    get_organization_documents,
    record_document_download,
    record_document_processing_assessment,
)
from apps.organizations.access_services import assign_platform_role
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    PlatformRoleCode,
)
from apps.payments.models import PaymentDirection, PaymentDocumentLink
from apps.payments.services import create_payment
from apps.projects.models import ProjectDocumentLink
from apps.projects.services import create_project


class DocumentServiceTests(TestCase):
    def setUp(self) -> None:
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            DOCUMENT_PROTECTED_ROOT=self.media_directory.name,
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(
            username="document-owner", password="test-password"
        )
        self.other_user = User.objects.create_user(
            username="other-document-user", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Document Company",
            slug="document-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Document Company",
            slug="other-document-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-DOCUMENT",
            name="Document project",
        )

    @staticmethod
    def _pdf_upload(
        name: str = "document.pdf", suffix: bytes = b""
    ) -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name,
            b"%PDF-1.7\ndocument" + suffix,
            content_type="application/pdf",
        )

    def _create_document(self, **kwargs):
        defaults = {
            "organization": self.organization,
            "actor": self.owner,
            "document_type": DocumentType.GENERAL,
            "title": "Project document",
            "reference": "DOC-001",
            "description": "Controlled private document",
            "upload": self._pdf_upload(),
            "target": self.project,
        }
        defaults.update(kwargs)
        return create_document(**defaults)

    def test_create_document_records_first_version_link_metadata_and_audit(
        self,
    ) -> None:
        payload = b"%PDF-1.7\ndocument"

        document = self._create_document()
        version = document.current_version

        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.original_file_name, "document.pdf")
        self.assertEqual(version.file_size, len(payload))
        self.assertEqual(version.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue(
            version.file.name.startswith(
                f"organizations/{self.organization.pk}/documents/{document.pk}/versions/"
            )
        )
        self.assertEqual(document.links.get().project, self.project)
        typed_link = ProjectDocumentLink.objects.get(document=document)
        self.assertEqual(typed_link.pk, document.links.get().pk)
        self.assertEqual(typed_link.legacy_link_id, document.links.get().pk)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_UPLOADED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_new_version_is_numbered_immutable_and_becomes_current(self) -> None:
        document = self._create_document()
        first_version = document.current_version

        second_version = add_document_version(
            document=document,
            actor=self.owner,
            upload=self._pdf_upload("corrected.pdf", b"-corrected"),
        )

        document.refresh_from_db()
        self.assertEqual(second_version.version_number, 2)
        self.assertEqual(document.current_version, second_version)
        self.assertEqual(document.versions.count(), 2)
        self.assertNotEqual(first_version.file.name, second_version.file.name)
        first_version.original_file_name = "changed.pdf"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            first_version.save()
        with self.assertRaisesMessage(ValidationError, "immutable"):
            first_version.delete()
        document.current_version = first_version
        with self.assertRaisesMessage(ValidationError, "آخرین نسخه"):
            document.save()

    def test_upload_validation_rejects_mismatched_type_and_signature(self) -> None:
        with self.assertRaisesMessage(
            ValueError, "نوع فایل بارگذاری‌شده با پسوند آن مطابقت ندارد."
        ):
            self._create_document(
                reference="DOC-BAD-TYPE",
                upload=SimpleUploadedFile(
                    "bad.pdf", b"not a PDF", content_type="image/jpeg"
                ),
            )
        with self.assertRaisesMessage(
            ValueError, "محتوای فایل بارگذاری‌شده معتبر نیست."
        ):
            self._create_document(
                reference="DOC-BAD-SIGNATURE",
                upload=SimpleUploadedFile(
                    "bad.pdf", b"not a PDF", content_type="application/pdf"
                ),
            )

    def test_document_link_requires_exactly_one_same_tenant_target(self) -> None:
        document = self._create_document()
        other_project = create_project(
            organization=self.other_organization,
            actor=self.other_user,
            code="P-OTHER",
            name="Other project",
        )

        with self.assertRaises(ValidationError):
            DocumentLink(organization=self.organization, document=document).full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            DocumentLink.objects.bulk_create(
                [DocumentLink(organization=self.organization, document=document)]
            )
        with self.assertRaises(ValidationError):
            DocumentLink(
                organization=self.organization,
                document=document,
                project=self.project,
                payment=self._payment(),
            ).full_clean()
        with self.assertRaises(PermissionDenied):
            add_document_link(
                document=document,
                actor=self.owner,
                target=other_project,
            )

    def _payment(self):
        return create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number=f"PAY-{self.organization.payments.count() + 1}",
            direction=PaymentDirection.DISBURSEMENT,
            amount=Decimal("75.00"),
            paid_on=date(2026, 9, 3),
            counterparty_name="Supplier LLC",
        )

    def test_add_link_supports_an_existing_financial_entity_and_audits(self) -> None:
        document = self._create_document()
        payment = self._payment()

        link = add_document_link(
            document=document,
            actor=self.owner,
            target=payment,
        )

        self.assertEqual(link.payment, payment)
        self.assertEqual(link.target_type, "payment")
        typed_link = PaymentDocumentLink.objects.get(document=document)
        self.assertEqual(typed_link.pk, link.pk)
        typed_link.payment = self._payment()
        with self.assertRaisesMessage(ValidationError, "تغییرپذیر نیست"):
            typed_link.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_LINK_ADDED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_document_access_requires_linked_context_permission(self) -> None:
        document = self._create_document()
        restricted_user = User.objects.create_user(username="document-only-user")
        role = OrganizationRole.objects.create(
            code="document_only", name="Document only"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
                    BusinessPermissionCode.DOCUMENTS_UPLOAD,
                ]
            )
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=restricted_user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )

        self.assertFalse(
            get_organization_documents(
                user=restricted_user, organization=self.organization
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            get_organization_document(
                user=restricted_user,
                organization=self.organization,
                document_id=str(document.pk),
            )
        form = DocumentCreateForm(
            organization=self.organization,
            user=restricted_user,
        )
        self.assertFalse(form.fields["project"].queryset.exists())

    def test_download_audit_is_version_specific_and_rechecks_access(self) -> None:
        document = self._create_document()
        version = document.current_version

        with self.assertRaises(PermissionDenied):
            record_document_download(version=version, actor=self.other_user)
        record_document_download(version=version, actor=self.owner)

        event = AuditEvent.objects.get(
            action=AuditAction.DOCUMENT_DOWNLOADED,
            entity_id=str(document.pk),
        )
        self.assertEqual(event.metadata["version_id"], str(version.pk))

    def test_archive_preserves_versions_and_links_and_removes_active_listing(
        self,
    ) -> None:
        document = self._create_document()

        archive_document(document=document, actor=self.owner, reason="Superseded")

        document.refresh_from_db()
        self.assertIsNotNone(document.archived_at)
        self.assertEqual(document.versions.count(), 1)
        self.assertEqual(document.links.count(), 1)
        self.assertFalse(
            get_organization_documents(user=self.owner, organization=self.organization)
            .filter(pk=document.pk)
            .exists()
        )

    def test_views_create_add_version_and_secure_download(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("documents:upload"),
            {
                "project": str(self.project.pk),
                "contract": "",
                "estimate": "",
                "expense": "",
                "payment": "",
                "daily_report": "",
                "document_type": DocumentType.RECEIPT,
                "title": "Uploaded receipt",
                "reference": "WEB-001",
                "description": "",
                "file": self._pdf_upload("uploaded.pdf"),
            },
        )

        document = self.organization.documents.get(reference="WEB-001")
        self.assertRedirects(
            response,
            reverse("documents:detail", kwargs={"document_id": document.pk}),
        )
        response = self.client.post(
            reverse("documents:version-add", kwargs={"document_id": document.pk}),
            {"file": self._pdf_upload("v2.pdf", b"-v2")},
        )
        self.assertRedirects(
            response,
            reverse("documents:detail", kwargs={"document_id": document.pk}),
        )
        document.refresh_from_db()
        self.assertEqual(document.current_version.version_number, 2)
        response = self.client.get(
            reverse("documents:download", kwargs={"document_id": document.pk})
        )
        self.assertEqual(response.status_code, 403)

        assigner = User.objects.create_superuser(username="storage-assigner")
        approver = User.objects.create_superuser(username="storage-approver")
        operator = User.objects.create_user(username="storage-operator")
        assign_platform_role(
            actor=assigner,
            approver=approver,
            target=operator,
            role=PlatformRoleCode.PLATFORM_OPERATIONS,
            reason="Document processing test duty",
        )
        record_document_processing_assessment(
            version=document.current_version,
            actor=operator,
            verdict="clean",
            adapter_code="test-scanner",
        )
        response = self.client.get(
            reverse("documents:download", kwargs={"document_id": document.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        response.close()

    def test_endpoints_reject_cross_tenant_document_uuid(self) -> None:
        other_project = create_project(
            organization=self.other_organization,
            actor=self.other_user,
            code="P-PRIVATE",
            name="Other private project",
        )
        other_document = self._create_document(
            organization=self.other_organization,
            actor=self.other_user,
            target=other_project,
            reference="OTHER-001",
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        detail_response = self.client.get(
            reverse("documents:detail", kwargs={"document_id": other_document.pk})
        )
        download_response = self.client.get(
            reverse("documents:download", kwargs={"document_id": other_document.pk})
        )
        archive_response = self.client.post(
            reverse("documents:archive", kwargs={"document_id": other_document.pk}),
            {"reason": "Unauthorized"},
        )

        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(download_response.status_code, 403)
        self.assertEqual(archive_response.status_code, 403)
