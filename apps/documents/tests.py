import hashlib
from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import DocumentType
from apps.documents.services import (
    archive_project_document,
    get_organization_documents,
    record_document_download,
    upload_project_document,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.payments.models import PaymentDirection
from apps.payments.services import create_payment
from apps.projects.services import create_project


class ProjectDocumentServiceTests(TestCase):
    def setUp(self) -> None:
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(
            username="document-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-document-user",
            password="test-password",
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
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-DOCUMENT",
            name="Document project",
        )

    @staticmethod
    def _pdf_upload(name: str = "receipt.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name,
            b"%PDF-1.7\nreceipt",
            content_type="application/pdf",
        )

    def test_upload_document_records_metadata_hash_and_audit(self) -> None:
        payload = b"%PDF-1.7\nreceipt"
        document = upload_project_document(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            document_type=DocumentType.RECEIPT,
            title="Concrete receipt",
            upload=self._pdf_upload(),
        )

        self.assertEqual(document.original_file_name, "receipt.pdf")
        self.assertEqual(document.file_size, len(payload))
        self.assertEqual(document.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue(
            document.file.name.startswith(
                f"organizations/{self.organization.pk}/projects/{self.project.pk}/"
            )
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_UPLOADED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_upload_rejects_mismatched_file_type(self) -> None:
        upload = SimpleUploadedFile(
            "receipt.pdf",
            b"not a PDF",
            content_type="image/jpeg",
        )

        with self.assertRaisesMessage(
            ValueError,
            "The uploaded file type does not match its extension.",
        ):
            upload_project_document(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                document_type=DocumentType.RECEIPT,
                title="Invalid receipt",
                upload=upload,
            )

    def test_upload_rejects_file_with_invalid_signature(self) -> None:
        upload = SimpleUploadedFile(
            "receipt.pdf",
            b"not a PDF",
            content_type="application/pdf",
        )

        with self.assertRaisesMessage(
            ValueError,
            "The uploaded file contents are not a valid file type.",
        ):
            upload_project_document(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                document_type=DocumentType.RECEIPT,
                title="Invalid receipt",
                upload=upload,
            )

    def test_upload_rejects_payment_from_another_project(self) -> None:
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-DOCUMENT-OTHER",
            name="Other document project",
        )
        payment = create_payment(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            payment_number="PAY-DOCUMENT-OTHER",
            direction=PaymentDirection.DISBURSEMENT,
            amount=Decimal("75.00"),
            paid_on=date(2026, 9, 3),
            counterparty_name="Supplier LLC",
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "The payment does not belong to this project.",
        ):
            upload_project_document(
                organization=self.organization,
                project=self.project,
                payment=payment,
                actor=self.owner,
                document_type=DocumentType.RECEIPT,
                title="Invalid receipt",
                upload=self._pdf_upload(),
            )

    def test_document_queryset_is_tenant_scoped(self) -> None:
        upload_project_document(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Visible document",
            upload=self._pdf_upload(),
        )

        documents = get_organization_documents(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(documents.values_list("title", flat=True)),
            ["Visible document"],
        )
        with self.assertRaises(PermissionDenied):
            get_organization_documents(
                user=self.other_user,
                organization=self.organization,
            )

    def test_document_download_audit_rechecks_access(self) -> None:
        document = upload_project_document(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Private document",
            upload=self._pdf_upload(),
        )

        with self.assertRaises(PermissionDenied):
            record_document_download(document=document, actor=self.other_user)

        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_DOWNLOADED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_archive_document_preserves_evidence_and_removes_active_listing(
        self,
    ) -> None:
        document = upload_project_document(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            document_type=DocumentType.RECEIPT,
            title="Archived receipt",
            upload=self._pdf_upload(),
        )

        archive_project_document(
            document=document,
            actor=self.owner,
            reason="Superseded by corrected receipt",
        )

        document.refresh_from_db()
        self.assertIsNotNone(document.archived_at)
        self.assertEqual(document.archive_reason, "Superseded by corrected receipt")
        self.assertEqual(document.archived_by, self.owner)
        self.assertFalse(
            get_organization_documents(
                user=self.owner,
                organization=self.organization,
            )
            .filter(pk=document.pk)
            .exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_ARCHIVED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_document_upload_and_download_views_are_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.other_organization.projects.create(
            code="P-DOCUMENT-HIDDEN",
            name="Hidden document project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        response = self.client.get(reverse("documents:upload"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, "Hidden document project")

        response = self.client.post(
            reverse("documents:upload"),
            {
                "project": str(self.project.pk),
                "payment": "",
                "document_type": DocumentType.RECEIPT,
                "title": "Uploaded receipt",
                "file": self._pdf_upload("uploaded.pdf"),
            },
        )

        self.assertRedirects(response, reverse("documents:list"))
        document = self.organization.project_documents.get(title="Uploaded receipt")
        response = self.client.get(
            reverse("documents:download", kwargs={"document_id": document.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_DOWNLOADED,
                entity_id=str(document.pk),
            ).exists()
        )

    def test_document_list_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("documents:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_document_endpoints_reject_cross_tenant_uuid(self) -> None:
        self.other_organization.memberships.create(
            user=self.other_user,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        other_project = create_project(
            organization=self.other_organization,
            actor=self.other_user,
            code="P-DOCUMENT-PRIVATE",
            name="Other private document project",
        )
        other_document = upload_project_document(
            organization=self.other_organization,
            project=other_project,
            actor=self.other_user,
            document_type=DocumentType.RECEIPT,
            title="Other private receipt",
            upload=self._pdf_upload("other-receipt.pdf"),
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
            {"reason": "Unauthorized attempt"},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(download_response.status_code, 404)
        self.assertEqual(archive_response.status_code, 404)
        other_document.refresh_from_db()
        self.assertIsNone(other_document.archived_at)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_DOWNLOADED,
                entity_id=str(other_document.pk),
            ).exists()
        )
