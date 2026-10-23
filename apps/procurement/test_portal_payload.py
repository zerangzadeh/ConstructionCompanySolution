"""PD-WC-D04 retained original, integrity, quarantine and rollback controls."""

import hashlib
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.documents.models import DocumentVersion
from apps.procurement.models import (
    QuoteRevisionEvidence,
    SupplierPortalSubmissionReceipt,
)
from apps.procurement.portal_services import submit_supplier_portal_quote
from apps.procurement.test_p5_s18_s22_supplier_portal import SupplierPortalFixtureMixin


class PortalPayloadTests(SupplierPortalFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        _, _, self.grant = self._accepted_grant()

    def upload(
        self,
        content=b"%PDF-1.4\noriginal quote\n%%EOF",
        name="bid.pdf",
        mime="application/pdf",
    ):
        return SimpleUploadedFile(name, content, content_type=mime)

    def submit(self, **kwargs):
        return submit_supplier_portal_quote(
            actor=self.external,
            grant=self.grant,
            upload=kwargs.pop("upload", self.upload()),
            idempotency_key="original-1",
            **kwargs,
        )

    def test_retained_bytes_digest_provenance_quarantine_and_no_tenant_membership(self):
        content = b"%PDF-1.4\noriginal quote\n%%EOF"
        receipt = self.submit()
        evidence = receipt.quote_revision.evidence_items.get()
        expected = hashlib.sha256(content).hexdigest()
        self.assertEqual(receipt.quote_revision.integrity_fingerprint, expected)
        self.assertEqual(evidence.canonical_sha256, expected)
        self.assertEqual(evidence.document_version.sha256, expected)
        self.assertEqual(evidence.source_channel, "external_portal_upload")
        with evidence.document_version.file.open("rb") as retained:
            self.assertEqual(retained.read(), content)
        self.assertEqual(evidence.sealed_custody.state, "quarantined")
        self.assertFalse(evidence.document_version.is_available)
        self.assertFalse(
            self.organization.memberships.filter(user=self.external).exists()
        )

    def test_client_digest_mismatch_rejects_without_receipt_or_retained_content(self):
        with self.assertRaises(ValueError):
            self.submit(integrity_fingerprint="a" * 64)
        self.assertFalse(SupplierPortalSubmissionReceipt.objects.exists())
        self.assertFalse(DocumentVersion.objects.exists())
        self.assertFalse(list(Path(settings.DOCUMENT_PROTECTED_ROOT).rglob("sealed-*")))

    def test_storage_or_evidence_failure_rolls_back_rows_and_cleans_files(self):
        with (
            patch.object(
                QuoteRevisionEvidence.objects,
                "create",
                side_effect=ValueError("failure"),
            ),
            self.assertRaises(ValueError),
        ):
            self.submit()
        self.assertFalse(SupplierPortalSubmissionReceipt.objects.exists())
        self.assertFalse(DocumentVersion.objects.exists())
        files = [
            p for p in Path(settings.DOCUMENT_PROTECTED_ROOT).rglob("*") if p.is_file()
        ]
        self.assertEqual(files, [])

    def test_replay_checks_actual_retained_content(self):
        receipt = self.submit()
        evidence = receipt.quote_revision.evidence_items.get()
        Path(evidence.document_version.file.path).write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.submit()
        self.assertEqual(SupplierPortalSubmissionReceipt.objects.count(), 1)

    def test_bad_mime_magic_empty_or_unsupported_file_rejected(self):
        for upload in [
            self.upload(b"not a PDF"),
            self.upload(b""),
            self.upload(mime="text/plain"),
            self.upload(name="bid.csv", mime="text/csv"),
        ]:
            with (
                self.subTest(name=upload.name, size=upload.size),
                self.assertRaises(ValueError),
            ):
                self.submit(upload=upload)
        self.assertFalse(SupplierPortalSubmissionReceipt.objects.exists())

    def test_expired_or_other_principal_cannot_stage_a_file(self):
        with self.assertRaises(PermissionDenied):
            submit_supplier_portal_quote(
                actor=self.outsider,
                grant=self.grant,
                upload=self.upload(),
                idempotency_key="denied",
            )
        self.assertFalse(list(Path(settings.DOCUMENT_PROTECTED_ROOT).rglob("*")))

    def test_docx_original_is_accepted_and_size_limit_cleans_staging(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            )
            archive.writestr("_rels/.rels", "<Relationships/>")
            archive.writestr(
                "word/document.xml", "<document>synthetic quote</document>"
            )
        payload = data.getvalue()
        receipt = self.submit(
            upload=self.upload(
                payload,
                "bid.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        )
        self.assertEqual(
            receipt.quote_revision.integrity_fingerprint,
            hashlib.sha256(payload).hexdigest(),
        )
        with (
            patch("apps.procurement.custody_services.MAX_EVIDENCE_ITEM_BYTES", 1),
            self.assertRaises(ValueError),
        ):
            self.submit()
        self.assertEqual(SupplierPortalSubmissionReceipt.objects.count(), 1)

    def test_http_requires_file_uses_multipart_and_hides_digest(self):
        self.client.force_login(self.external)
        url = reverse("procurement:portal_context", args=[self.grant.pk])
        response = self.client.get(url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertEqual(response.content.count(b"<main"), 1)
        self.assertNotContains(response, 'name="integrity_fingerprint"')
        submit_url = reverse("procurement:portal_submit", args=[self.grant.pk])
        self.assertEqual(
            self.client.post(submit_url, {"idempotency_key": "http"}).status_code, 400
        )
        response = self.client.post(
            submit_url, {"idempotency_key": "http", "upload": self.upload()}
        )
        self.assertEqual(response.status_code, 302)

    def test_http_rejects_multiple_originals_and_mismatched_comparison_digest(self):
        self.client.force_login(self.external)
        url = reverse("procurement:portal_submit", args=[self.grant.pk])
        response = self.client.post(
            url, {"idempotency_key": "multi", "upload": [self.upload(), self.upload()]}
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            url,
            {
                "idempotency_key": "mismatch",
                "upload": self.upload(),
                "integrity_fingerprint": "a" * 64,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SupplierPortalSubmissionReceipt.objects.exists())
