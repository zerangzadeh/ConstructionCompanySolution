import hashlib
import io
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.admin import DocumentAdmin, DocumentVersionAdmin
from apps.documents.models import (
    Document,
    DocumentRetentionClassification,
    DocumentVersion,
    SealedCustodyState,
    SealedDocumentCustody,
)
from apps.documents.services import (
    add_document_version,
    archive_document,
    compare_document_versions,
    create_document_export_manifest,
    get_document_version_for_download,
    get_organization_document,
    get_organization_documents,
    request_document_disposal,
    search_organization_documents,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.procurement.custody_services import (
    MAX_EVIDENCE_ITEM_BYTES,
    MAX_SEALED_PACKAGE_BYTES,
    MAX_SUPPLIER_ATTACHMENTS,
    custody_sealed_quote_evidence,
)
from apps.procurement.models import (
    QuoteEvidenceSourceChannel,
    QuoteEvidenceType,
    QuoteRevision,
    QuoteRevisionEvidence,
)
from apps.procurement.quote_services import (
    capture_quote_revision,
    submit_quote_revision,
)
from apps.procurement.rfq_services import (
    add_rfq_line,
    close_rfq,
    create_rfq,
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.projects.models import Project


def _pdf_upload(name: str = "supplier-price.pdf", content: bytes | None = None):
    return SimpleUploadedFile(
        name,
        content or b"%PDF-1.7\nsealed supplier bytes\n%%EOF",
        content_type="application/pdf",
    )


def _docx_upload(name: str = "commercial-annex.docx"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", "<document/>")
    return SimpleUploadedFile(
        name,
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


class SealedCustodyFixtureMixin(ProcurementFixtureMixin):
    def setUp(self) -> None:
        super().setUp()
        self._protected_root = tempfile.TemporaryDirectory()
        self._protected_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self._protected_root.name
        )
        self._protected_override.enable()
        self.addCleanup(self._protected_override.disable)
        self.addCleanup(self._protected_root.cleanup)

    def _grant(self, code: BusinessPermissionCode, user=None) -> None:
        membership = self.organization.memberships.get(user=user or self.owner)
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=code)
        )

    def _closed_revision(self):
        OrganizationSettings.objects.get_or_create(organization=self.organization)
        request, item = self.create_approved_request()
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=request,
            rfq_number="RFQ-CUSTODY-001",
            title="Sealed custody",
            closing_at=now + timedelta(days=2),
            earliest_opening_at=now + timedelta(days=2),
        )
        add_rfq_line(
            organization=self.organization,
            actor=self.member,
            rfq=rfq,
            purchase_request_item=item,
            quantity=Decimal("10.0000"),
        )
        submit_rfq_for_issue(organization=self.organization, actor=self.member, rfq=rfq)
        version = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="custody-issue",
        )
        revision = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=version.invitations.get(),
            integrity_fingerprint="a" * 64,
            source_channel="manual_capture",
            idempotency_key="custody-capture",
        )
        submit_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=revision,
            idempotency_key="custody-submit",
        )
        self._grant(BusinessPermissionCode.RFQS_CLOSE_CUSTODY)
        with patch(
            "apps.procurement.rfq_services.timezone.now",
            return_value=version.closing_at + timedelta(seconds=1),
        ):
            manifest = close_rfq(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                idempotency_key="custody-close",
            )
        return revision, manifest

    def _accept_original(self, revision, *, key="original-001", actor=None):
        return custody_sealed_quote_evidence(
            organization=self.organization,
            actor=actor or self.owner,
            quote_revision=revision,
            evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
            evidence_slot="ignored-for-original",
            upload=_pdf_upload(),
            idempotency_key=key,
        )


class SealedCustodyTests(SealedCustodyFixtureMixin, TestCase):
    def test_accepts_one_immutable_original_without_mutating_close_manifest(self):
        revision, manifest = self._closed_revision()
        manifest_snapshot = (
            manifest.payload_fingerprint,
            manifest.entries.count(),
            manifest.entries.get().effective_revision_id,
        )
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)

        evidence = self._accept_original(revision)

        self.assertEqual(evidence.evidence_slot, "primary")
        self.assertEqual(
            evidence.source_channel,
            QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE,
        )
        self.assertEqual(evidence.revision_fingerprint, revision.integrity_fingerprint)
        self.assertEqual(evidence.canonical_sha256, evidence.document_version.sha256)
        self.assertEqual(
            evidence.document.retention_classification,
            DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE,
        )
        self.assertEqual(evidence.sealed_custody.state, SealedCustodyState.QUARANTINED)
        self.assertFalse(evidence.document_version.is_available)
        manifest.refresh_from_db()
        self.assertEqual(
            (
                manifest.payload_fingerprint,
                manifest.entries.count(),
                manifest.entries.get().effective_revision_id,
            ),
            manifest_snapshot,
        )
        evidence.evidence_slot = "changed"
        with self.assertRaises(ValidationError):
            evidence.save()
        with self.assertRaises(ValidationError):
            QuoteRevisionEvidence.objects.filter(pk=evidence.pk).update(
                evidence_slot="changed"
            )

        event = AuditEvent.objects.get(action=AuditAction.RFQ_SEALED_EVIDENCE_CUSTODIED)
        serialized = str(event.metadata).lower()
        self.assertNotIn("supplier-price", serialized)
        self.assertNotIn("sealed supplier bytes", serialized)
        self.assertEqual(event.metadata["custody_state"], "quarantined")

    def test_permission_has_no_owner_admin_platform_or_uploader_bypass(self):
        revision, _ = self._closed_revision()
        admin_user = User.objects.create_user(username="custody-admin")
        self.organization.memberships.create(
            user=admin_user,
            role=MembershipRole.TENANT_ADMIN,
            status=MembershipStatus.ACTIVE,
        )
        platform_user = User.objects.create_superuser(
            username="custody-platform", password="x"
        )
        for actor in (self.owner, self.member, admin_user, platform_user):
            with (
                self.subTest(actor=actor.username),
                self.assertRaises(PermissionDenied),
            ):
                self._accept_original(
                    revision, key=f"denied-{actor.username}", actor=actor
                )
        self.assertFalse(QuoteRevisionEvidence.objects.exists())
        self.assertFalse(
            Document.objects.filter(current_version__isnull=False).exists()
        )

    def test_permission_is_intersected_with_project_scope(self):
        revision, _ = self._closed_revision()
        self._grant(
            BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE, user=self.member
        )
        membership = self.organization.memberships.get(user=self.member)
        other_project = Project.objects.create(
            organization=self.organization, code="OTHER-CUSTODY", name="Other"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=membership.role_definition,
            reason="P5-S08 scope test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=other_project,
            reason="P5-S08 scope test",
        )
        type(membership).objects.filter(pk=membership.pk).update(
            authorization_migrated_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self._accept_original(revision, actor=self.member)

    def test_idempotency_hash_validation_ooxml_and_attachment_identity(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        payload = b"%PDF-1.7\nsealed supplier bytes\n%%EOF"
        expected = hashlib.sha256(payload).hexdigest()
        first = custody_sealed_quote_evidence(
            organization=self.organization,
            actor=self.owner,
            quote_revision=revision,
            evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
            evidence_slot="primary",
            upload=_pdf_upload(content=payload),
            idempotency_key="same-item",
            expected_sha256=expected,
        )
        retry = custody_sealed_quote_evidence(
            organization=self.organization,
            actor=self.owner,
            quote_revision=revision,
            evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
            evidence_slot="primary",
            upload=_pdf_upload(content=payload),
            idempotency_key="same-item",
            expected_sha256=expected,
        )
        self.assertEqual(first.pk, retry.pk)
        self.assertEqual(DocumentVersion.objects.count(), 1)

        with self.assertRaises(ValueError):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="annex-a",
                upload=_pdf_upload(content=b"%PDF-1.7\ndifferent\n%%EOF"),
                idempotency_key="same-item",
            )
        attachment = custody_sealed_quote_evidence(
            organization=self.organization,
            actor=self.owner,
            quote_revision=revision,
            evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
            evidence_slot="annex-a",
            upload=_docx_upload(),
            idempotency_key="attachment-001",
        )
        self.assertEqual(attachment.evidence_type, "supplier_attachment")
        with self.assertRaises(ValueError):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="annex-b",
                upload=_pdf_upload(),
                idempotency_key="bad-hash",
                expected_sha256="f" * 64,
            )
        self.assertEqual(QuoteRevisionEvidence.objects.count(), 2)

    def test_file_policy_fails_closed_with_redacted_audit(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        invalid = SimpleUploadedFile(
            "commercial.pdf", b"not-a-pdf", content_type="application/pdf"
        )
        with self.assertRaises(ValueError):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
                evidence_slot="primary",
                upload=invalid,
                idempotency_key="invalid-signature",
            )
        event = AuditEvent.objects.get(action=AuditAction.RFQ_SEALED_EVIDENCE_REJECTED)
        serialized = str(event.metadata).lower()
        self.assertNotIn("commercial.pdf", serialized)
        self.assertNotIn("not-a-pdf", serialized)
        self.assertFalse(event.metadata["content_recorded"])
        self.assertFalse(QuoteRevisionEvidence.objects.exists())

    def test_code_owned_item_count_and_package_limits_fail_closed(self):
        self.assertEqual(MAX_EVIDENCE_ITEM_BYTES, 25 * 1024 * 1024)
        self.assertEqual(MAX_SEALED_PACKAGE_BYTES, 100 * 1024 * 1024)
        self.assertEqual(MAX_SUPPLIER_ATTACHMENTS, 20)
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        with self.assertRaises(ValueError):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="before-original",
                upload=_pdf_upload(),
                idempotency_key="before-original",
            )
        original = self._accept_original(revision)
        with patch("apps.procurement.custody_services.MAX_SUPPLIER_ATTACHMENTS", 1):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="limit-1",
                upload=_pdf_upload(),
                idempotency_key="limit-1",
            )
            with self.assertRaises(ValueError):
                custody_sealed_quote_evidence(
                    organization=self.organization,
                    actor=self.owner,
                    quote_revision=revision,
                    evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                    evidence_slot="limit-2",
                    upload=_pdf_upload(),
                    idempotency_key="limit-2",
                )
        with (
            patch(
                "apps.procurement.custody_services.MAX_SEALED_PACKAGE_BYTES",
                original.document_version.file_size,
            ),
            self.assertRaises(ValueError),
        ):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="package-overflow",
                upload=_pdf_upload(),
                idempotency_key="package-overflow",
            )
        with (
            patch("apps.procurement.custody_services.MAX_EVIDENCE_ITEM_BYTES", 8),
            self.assertRaises(ValueError),
        ):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="item-overflow",
                upload=_pdf_upload(),
                idempotency_key="item-overflow",
            )

    def test_sealed_content_is_denied_from_generic_document_paths_and_admin(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        evidence = self._accept_original(revision)

        self.assertFalse(
            get_organization_documents(
                user=self.owner, organization=self.organization
            ).filter(pk=evidence.document_id)
        )
        self.assertFalse(
            search_organization_documents(
                user=self.owner,
                organization=self.organization,
                query="supplier-price",
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            get_organization_document(
                user=self.owner,
                organization=self.organization,
                document_id=str(evidence.document_id),
            )
        denied_calls = (
            lambda: get_document_version_for_download(
                document=evidence.document,
                version_id=str(evidence.document_version_id),
                actor=self.owner,
            ),
            lambda: compare_document_versions(
                document=evidence.document,
                actor=self.owner,
                left_version_id=evidence.document_version_id,
                right_version_id=evidence.document_version_id,
            ),
            lambda: add_document_version(
                document=evidence.document, actor=self.owner, upload=_pdf_upload()
            ),
            lambda: archive_document(
                document=evidence.document, actor=self.owner, reason="not permitted"
            ),
            lambda: create_document_export_manifest(
                organization=self.organization,
                actor=self.owner,
                document_ids=[evidence.document_id],
            ),
            lambda: request_document_disposal(
                document=evidence.document, actor=self.owner, reason="not permitted"
            ),
        )
        for call in denied_calls:
            with self.assertRaises(PermissionDenied):
                call()

        request = RequestFactory().get("/admin/")
        request.user = self.owner
        self.assertFalse(
            DocumentAdmin(Document, admin.site)
            .get_queryset(request)
            .filter(pk=evidence.document_id)
            .exists()
        )
        self.assertFalse(
            DocumentVersionAdmin(
                DocumentVersion,
                admin.site,
            )
            .get_queryset(request)
            .filter(pk=evidence.document_version_id)
            .exists()
        )

    def test_audit_failure_rolls_back_database_and_protected_bytes(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        with tempfile.TemporaryDirectory() as protected_root:
            with (
                override_settings(DOCUMENT_PROTECTED_ROOT=protected_root),
                patch(
                    "apps.procurement.custody_services.record_audit_event",
                    side_effect=RuntimeError("audit unavailable"),
                ),
                self.assertRaises(RuntimeError),
            ):
                self._accept_original(revision)
            remaining_files = [
                path for path in Path(protected_root).rglob("*") if path.is_file()
            ]
        self.assertEqual(remaining_files, [])
        self.assertFalse(QuoteRevisionEvidence.objects.exists())
        self.assertFalse(SealedDocumentCustody.objects.exists())
        self.assertFalse(DocumentVersion.objects.exists())

    def test_cross_tenant_target_is_denied_without_business_evidence(self):
        revision, _ = self._closed_revision()
        with self.assertRaises(PermissionDenied):
            custody_sealed_quote_evidence(
                organization=self.other_organization,
                actor=self.outsider,
                quote_revision=revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
                evidence_slot="primary",
                upload=_pdf_upload(),
                idempotency_key="cross-tenant",
            )
        self.assertFalse(QuoteRevisionEvidence.objects.exists())


class SealedCustodyConcurrencyTests(SealedCustodyFixtureMixin, TransactionTestCase):
    def test_equivalent_retries_converge_and_distinct_attachments_do_not_collapse(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        barrier = Barrier(2)

        def accept_original() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                evidence = custody_sealed_quote_evidence(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    quote_revision=QuoteRevision.objects.get(pk=revision.pk),
                    evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL,
                    evidence_slot="primary",
                    upload=_pdf_upload(),
                    idempotency_key="concurrent-original",
                )
                return str(evidence.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            original_ids = list(pool.map(lambda _: accept_original(), range(2)))
        self.assertEqual(original_ids[0], original_ids[1])
        self.assertEqual(QuoteRevisionEvidence.objects.count(), 1)

        attachment_barrier = Barrier(2)

        def accept_attachment(index: int) -> str:
            close_old_connections()
            try:
                attachment_barrier.wait(timeout=10)
                evidence = custody_sealed_quote_evidence(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    quote_revision=QuoteRevision.objects.get(pk=revision.pk),
                    evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                    evidence_slot=f"concurrent-{index}",
                    upload=_pdf_upload(content=f"%PDF-1.7\n{index}\n%%EOF".encode()),
                    idempotency_key=f"concurrent-attachment-{index}",
                )
                return str(evidence.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            attachment_ids = list(pool.map(accept_attachment, range(2)))
        self.assertNotEqual(attachment_ids[0], attachment_ids[1])
        self.assertEqual(QuoteRevisionEvidence.objects.count(), 3)
