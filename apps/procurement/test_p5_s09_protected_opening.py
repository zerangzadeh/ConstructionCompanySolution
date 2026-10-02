import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
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
)
from apps.procurement.custody_services import custody_sealed_quote_evidence
from apps.procurement.models import (
    QuoteConfidentialAccessGrant,
    QuoteConfidentialAccessRevocation,
    QuoteEvidencePackageFreeze,
    QuoteEvidenceType,
    QuoteOpeningEvent,
    QuoteOpeningRequest,
    QuoteRevision,
)
from apps.procurement.opening_services import (
    approve_quote_opening,
    deliver_quote_confidential_document,
    grant_quote_confidential_access,
    request_quote_opening,
    revoke_quote_confidential_access,
)
from apps.procurement.test_p5_s08_sealed_custody import (
    SealedCustodyFixtureMixin,
    _pdf_upload,
)
from apps.projects.models import Project


class ProtectedOpeningTests(SealedCustodyFixtureMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.revision, self.manifest = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        self.evidence = self._accept_original(self.revision)
        self.opening_time = self.revision.rfq_version.earliest_opening_at + timedelta(
            seconds=1
        )

    def _grant_permission(self, user: User, code: BusinessPermissionCode) -> None:
        membership = self.organization.memberships.get(user=user)
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=code)
        )

    def _make_actor(self, username: str, role: str) -> User:
        user = User.objects.create_user(username=username)
        self.organization.memberships.create(
            user=user,
            role=role,
            status=MembershipStatus.ACTIVE,
        )
        return user

    def _request(self, *, actor=None, key="open-request-1", reason="scheduled opening"):
        with patch(
            "apps.procurement.opening_services.timezone.now",
            return_value=self.opening_time,
        ):
            return request_quote_opening(
                organization=self.organization,
                actor=actor or self.owner,
                quote_revision=self.revision,
                reason=reason,
                idempotency_key=key,
            )

    def _mark_clean(self) -> None:
        for item in self.revision.evidence_items.select_related("document_version"):
            DocumentProcessingAssessment.objects.create(
                organization=self.organization,
                version=item.document_version,
                sequence=1,
                verdict=DocumentProcessingVerdict.CLEAN,
                input_sha256=item.canonical_sha256,
                adapter_code="p5-s09-test-scanner",
                adapter_version="1",
                recorded_by=self.owner,
            )

    def _approve(self, opening_request, actor):
        with patch(
            "apps.procurement.opening_services.timezone.now",
            return_value=self.opening_time,
        ):
            return approve_quote_opening(
                organization=self.organization,
                actor=actor,
                opening_request=opening_request,
            )

    def test_request_permanently_freezes_exact_package_and_is_idempotent(self):
        self._grant_permission(self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        opening_request = self._request()
        retry = self._request()

        self.assertEqual(opening_request.pk, retry.pk)
        package = QuoteEvidencePackageFreeze.objects.get(quote_revision=self.revision)
        self.assertEqual(package.close_manifest_id, self.manifest.pk)
        self.assertEqual(package.item_count, 1)
        frozen = package.items.get()
        self.assertEqual(frozen.evidence_id, self.evidence.pk)
        self.assertEqual(frozen.document_version_id, self.evidence.document_version_id)
        self.assertEqual(frozen.canonical_sha256, self.evidence.canonical_sha256)
        with self.assertRaises(ValueError):
            self._request(reason="different payload")
        with self.assertRaises(ValueError):
            custody_sealed_quote_evidence(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT,
                evidence_slot="post-freeze",
                upload=_pdf_upload("post-freeze.pdf"),
                idempotency_key="post-freeze",
            )
        self.assertEqual(self.manifest.entries.count(), 1)
        package.item_count = 2
        with self.assertRaises(ValidationError):
            package.save()

    def test_earliest_boundary_permission_and_cross_tenant_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            self._request()
        self._grant_permission(self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        with (
            patch(
                "apps.procurement.opening_services.timezone.now",
                return_value=self.revision.rfq_version.earliest_opening_at
                - timedelta(seconds=1),
            ),
            self.assertRaises(ValueError),
        ):
            request_quote_opening(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                reason="too early",
                idempotency_key="too-early",
            )
        with self.assertRaises(PermissionDenied):
            request_quote_opening(
                organization=self.other_organization,
                actor=self.outsider,
                quote_revision=self.revision,
                reason="cross tenant",
                idempotency_key="cross-tenant",
            )
        self.assertFalse(QuoteOpeningRequest.objects.exists())

    def test_opening_permission_is_intersected_with_exact_project_scope(self):
        self._grant_permission(self.member, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        membership = self.organization.memberships.get(user=self.member)
        other_project = Project.objects.create(
            organization=self.organization,
            code="OTHER-OPENING",
            name="Other opening project",
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=membership.role_definition,
            reason="P5-S09 scope test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=other_project,
            reason="P5-S09 scope test",
        )
        type(membership).objects.filter(pk=membership.pk).update(
            authorization_migrated_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self._request(actor=self.member, key="wrong-project")
        self.assertFalse(QuoteEvidencePackageFreeze.objects.exists())

    def test_independent_approval_requires_clean_package_and_is_immutable(self):
        approver = self._make_actor("opening-approver", MembershipRole.TENANT_MANAGER)
        self._grant_permission(self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        self._grant_permission(approver, BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN)
        opening_request = self._request()

        self._grant_permission(
            self.owner, BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN
        )
        with self.assertRaises(PermissionDenied):
            self._approve(opening_request, self.owner)
        with self.assertRaises(ValueError):
            self._approve(opening_request, approver)
        self._mark_clean()
        event = self._approve(opening_request, approver)
        retry = self._approve(opening_request, approver)

        self.assertEqual(event.pk, retry.pk)
        self.assertEqual(event.opening_request_id, opening_request.pk)
        self.assertNotEqual(opening_request.requested_by_id, event.approved_by_id)
        event.package_fingerprint = "f" * 64
        with self.assertRaises(ValidationError):
            event.save()
        self.assertEqual(QuoteOpeningEvent.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            deliver_quote_confidential_document(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                evidence=self.evidence,
            )

    def test_audit_failure_rolls_back_opening_event(self):
        approver = self._make_actor("audit-approver", MembershipRole.TENANT_MANAGER)
        self._grant_permission(self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        self._grant_permission(approver, BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN)
        opening_request = self._request()
        self._mark_clean()
        with (
            patch(
                "apps.procurement.opening_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self._approve(opening_request, approver)
        self.assertFalse(QuoteOpeningEvent.objects.exists())

    def test_revision_grant_delivery_and_revocation_enforce_least_privilege(self):
        approver = self._make_actor("delivery-approver", MembershipRole.TENANT_MANAGER)
        viewer = self._make_actor("confidential-viewer", MembershipRole.VIEWER)
        self._grant_permission(self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN)
        self._grant_permission(
            self.owner,
            BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
        )
        self._grant_permission(approver, BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN)
        self._grant_permission(
            viewer, BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL
        )
        opening_request = self._request()
        self._mark_clean()
        self._approve(opening_request, approver)
        viewer_membership = self.organization.memberships.get(user=viewer)

        with self.assertRaises(PermissionDenied):
            deliver_quote_confidential_document(
                organization=self.organization,
                actor=viewer,
                quote_revision=self.revision,
                evidence=self.evidence,
            )
        with self.assertRaises(PermissionDenied):
            grant_quote_confidential_access(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                membership=self.organization.memberships.get(user=self.owner),
                reason="self grant",
                idempotency_key="self-grant",
            )
        grant = grant_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            quote_revision=self.revision,
            membership=viewer_membership,
            reason="opening team access",
            idempotency_key="viewer-grant",
        )
        delivery = deliver_quote_confidential_document(
            organization=self.organization,
            actor=viewer,
            quote_revision=self.revision,
            evidence=self.evidence,
        )
        self.assertEqual(delivery.content, _pdf_upload().read())
        self.assertEqual(delivery.filename, "supplier-price.pdf")
        self.assertTrue(delivery.content_disposition.startswith("attachment;"))
        self.assertTrue(delivery.nosniff)
        revocation = revoke_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="access complete",
        )
        self.assertTrue(
            QuoteConfidentialAccessGrant.objects.filter(pk=grant.pk).exists()
        )
        self.assertTrue(
            QuoteConfidentialAccessRevocation.objects.filter(pk=revocation.pk).exists()
        )
        with self.assertRaises(PermissionDenied):
            deliver_quote_confidential_document(
                organization=self.organization,
                actor=viewer,
                quote_revision=self.revision,
                evidence=self.evidence,
            )

        audit_text = " ".join(
            str(metadata)
            for metadata in AuditEvent.objects.filter(
                action__in=[
                    AuditAction.RFQ_CONFIDENTIAL_CONTENT_ACCESSED,
                    AuditAction.RFQ_CONFIDENTIAL_CONTENT_DENIED,
                ]
            ).values_list("metadata", flat=True)
        ).lower()
        self.assertNotIn("supplier-price", audit_text)
        self.assertNotIn("sealed supplier bytes", audit_text)

    def test_hash_or_latest_non_clean_assessment_blocks_access(self):
        approver = self._make_actor("hash-approver", MembershipRole.TENANT_MANAGER)
        viewer = self._make_actor("hash-viewer", MembershipRole.VIEWER)
        for user, code in (
            (self.owner, BusinessPermissionCode.RFQ_QUOTES_OPEN),
            (
                self.owner,
                BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
            ),
            (approver, BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN),
            (viewer, BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL),
        ):
            self._grant_permission(user, code)
        opening_request = self._request()
        self._mark_clean()
        self._approve(opening_request, approver)
        grant_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            quote_revision=self.revision,
            membership=self.organization.memberships.get(user=viewer),
            reason="technical test",
            idempotency_key="technical-viewer",
        )
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=self.evidence.document_version,
            sequence=2,
            verdict=DocumentProcessingVerdict.UNSAFE,
            input_sha256=self.evidence.canonical_sha256,
            adapter_code="p5-s09-test-scanner",
            adapter_version="2",
            recorded_by=self.owner,
        )
        with self.assertRaises(ValueError):
            deliver_quote_confidential_document(
                organization=self.organization,
                actor=viewer,
                quote_revision=self.revision,
                evidence=self.evidence,
            )

    def test_no_generic_storage_url_or_filesystem_path_is_returned(self):
        with (
            tempfile.TemporaryDirectory() as protected_root,
            override_settings(DOCUMENT_PROTECTED_ROOT=protected_root),
        ):
            self.assertNotIn(protected_root, str(self.evidence.document_version.file))
        with self.assertRaises(ValueError):
            self.evidence.document_version.file.storage.url(
                self.evidence.document_version.file.name
            )


class ProtectedOpeningConcurrencyTests(SealedCustodyFixtureMixin, TransactionTestCase):
    def test_equivalent_request_and_approval_retries_converge(self):
        revision, _ = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        self._accept_original(revision)
        self._grant(BusinessPermissionCode.RFQ_QUOTES_OPEN)
        opening_time = revision.rfq_version.earliest_opening_at + timedelta(seconds=1)
        barrier = Barrier(2)

        def create_request() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                request = request_quote_opening(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    quote_revision=QuoteRevision.objects.get(pk=revision.pk),
                    reason="concurrent opening",
                    idempotency_key="concurrent-opening",
                )
                return str(request.pk)
            finally:
                close_old_connections()

        with (
            patch(
                "apps.procurement.opening_services.timezone.now",
                return_value=opening_time,
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            request_ids = list(pool.map(lambda _: create_request(), range(2)))

        self.assertEqual(request_ids[0], request_ids[1])
        self.assertEqual(QuoteEvidencePackageFreeze.objects.count(), 1)
        self.assertEqual(QuoteOpeningRequest.objects.count(), 1)

        approver = User.objects.create_user(username="concurrent-approver")
        approver_membership = self.organization.memberships.create(
            user=approver,
            role=MembershipRole.TENANT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        approver_membership.role_definition.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN
            )
        )
        evidence = revision.evidence_items.select_related("document_version").get()
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=evidence.document_version,
            sequence=1,
            verdict=DocumentProcessingVerdict.CLEAN,
            input_sha256=evidence.canonical_sha256,
            adapter_code="p5-s09-concurrency-scanner",
            adapter_version="1",
            recorded_by=self.owner,
        )
        approval_barrier = Barrier(2)

        def approve_request() -> str:
            close_old_connections()
            try:
                approval_barrier.wait(timeout=10)
                event = approve_quote_opening(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=approver.pk),
                    opening_request=QuoteOpeningRequest.objects.get(pk=request_ids[0]),
                )
                return str(event.pk)
            finally:
                close_old_connections()

        with (
            patch(
                "apps.procurement.opening_services.timezone.now",
                return_value=opening_time,
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            event_ids = list(pool.map(lambda _: approve_request(), range(2)))

        self.assertEqual(event_ids[0], event_ids[1])
        self.assertEqual(QuoteOpeningEvent.objects.count(), 1)
