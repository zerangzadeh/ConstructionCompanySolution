from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
)
from apps.procurement.models import (
    QuoteRevisionStatus,
    SupplierPortalGrant,
    SupplierPortalGrantRevocation,
    SupplierPortalInvitation,
    SupplierPortalSubmissionReceipt,
)
from apps.procurement.portal_services import (
    accept_supplier_portal_invitation,
    create_supplier_portal_invitation,
    get_supplier_portal_rfq_context,
    revoke_supplier_portal_grant,
    submit_supplier_portal_quote,
)
from apps.procurement.test_quotes import QuoteFixtureMixin


class SupplierPortalFixtureMixin(QuoteFixtureMixin):
    def setUp(self) -> None:
        super().setUp()
        self.external = User.objects.create_user(
            username="external-supplier", email="supplier@example.test"
        )

    def _grant_internal_management(self) -> None:
        membership = self.organization.memberships.get(user=self.owner)
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE
            )
        )

    def _accepted_grant(self):
        self._grant_internal_management()
        rfq_invitation = self._issued_invitation()
        portal_invitation, token = create_supplier_portal_invitation(
            organization=self.organization,
            actor=self.owner,
            rfq_invitation=rfq_invitation,
            invited_email=self.external.email,
            expires_at=timezone.now() + timedelta(days=1),
        )
        grant = accept_supplier_portal_invitation(actor=self.external, token=token)
        return rfq_invitation, portal_invitation, grant


class SupplierPortalFoundationTests(SupplierPortalFixtureMixin, TestCase):
    def test_invitation_management_is_default_ungranted_and_token_hash_only(self):
        rfq_invitation = self._issued_invitation()
        with self.assertRaises(PermissionDenied):
            create_supplier_portal_invitation(
                organization=self.organization,
                actor=self.owner,
                rfq_invitation=rfq_invitation,
                invited_email=self.external.email,
                expires_at=timezone.now() + timedelta(days=1),
            )
        self._grant_internal_management()
        invitation, token = create_supplier_portal_invitation(
            organization=self.organization,
            actor=self.owner,
            rfq_invitation=rfq_invitation,
            invited_email=self.external.email,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertNotEqual(invitation.token_hash, token)
        self.assertNotIn(token, invitation.token_hash)
        self.assertEqual(SupplierPortalInvitation.objects.count(), 1)

    def test_acceptance_creates_no_membership_and_context_is_exact_scope(self):
        rfq_invitation, _, grant = self._accepted_grant()
        self.assertFalse(
            self.organization.memberships.filter(user=self.external).exists()
        )
        context = get_supplier_portal_rfq_context(actor=self.external, grant=grant)
        self.assertEqual(
            context["rfq_number"], rfq_invitation.rfq_version.rfq.rfq_number
        )
        self.assertEqual(len(context["lines"]), 1)
        self.assertNotIn("purchase_request", context)
        with self.assertRaises(PermissionDenied):
            get_supplier_portal_rfq_context(actor=self.outsider, grant=grant)

    def test_email_impersonation_and_cross_tenant_invitation_are_denied(self):
        self._grant_internal_management()
        rfq_invitation = self._issued_invitation()
        _, token = create_supplier_portal_invitation(
            organization=self.organization,
            actor=self.owner,
            rfq_invitation=rfq_invitation,
            invited_email=self.external.email,
            expires_at=timezone.now() + timedelta(days=1),
        )
        impostor = User.objects.create_user(
            username="portal-impostor", email="impostor@example.test"
        )
        with self.assertRaises(PermissionDenied):
            accept_supplier_portal_invitation(actor=impostor, token=token)
        with self.assertRaises(PermissionDenied):
            create_supplier_portal_invitation(
                organization=self.other_organization,
                actor=self.outsider,
                rfq_invitation=rfq_invitation,
                invited_email=self.external.email,
                expires_at=timezone.now() + timedelta(hours=1),
            )

    def test_submission_reuses_quote_revision_and_is_idempotent(self):
        _, _, grant = self._accepted_grant()
        receipt = submit_supplier_portal_quote(
            actor=self.external,
            grant=grant,
            integrity_fingerprint="a" * 64,
            source_reference="SUPPLIER-1",
            idempotency_key="portal-submit-1",
        )
        retry = submit_supplier_portal_quote(
            actor=self.external,
            grant=grant,
            integrity_fingerprint="a" * 64,
            source_reference="SUPPLIER-1",
            idempotency_key="portal-submit-1",
        )
        self.assertEqual(receipt.pk, retry.pk)
        self.assertEqual(receipt.quote_revision.status, QuoteRevisionStatus.SUBMITTED)
        self.assertEqual(receipt.quote_revision.source_channel, "external_portal")
        with self.assertRaises(ValueError):
            submit_supplier_portal_quote(
                actor=self.external,
                grant=grant,
                integrity_fingerprint="b" * 64,
                source_reference="SUPPLIER-1",
                idempotency_key="portal-submit-1",
            )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPLIER_PORTAL_QUOTE_SUBMITTED,
                organization=self.organization,
            ).exists()
        )

    def test_new_submission_supersedes_without_mutating_history(self):
        _, _, grant = self._accepted_grant()
        first = submit_supplier_portal_quote(
            actor=self.external,
            grant=grant,
            integrity_fingerprint="a" * 64,
            idempotency_key="portal-submit-1",
        )
        second = submit_supplier_portal_quote(
            actor=self.external,
            grant=grant,
            integrity_fingerprint="b" * 64,
            idempotency_key="portal-submit-2",
        )
        first.quote_revision.refresh_from_db()
        self.assertEqual(first.quote_revision.status, QuoteRevisionStatus.SUPERSEDED)
        self.assertEqual(second.quote_revision.supersedes_id, first.quote_revision_id)
        with self.assertRaises(ValidationError):
            first.save()

    def test_revocation_is_append_only_and_immediately_denies_access(self):
        _, _, grant = self._accepted_grant()
        revocation = revoke_supplier_portal_grant(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="Supplier representative changed",
        )
        retry = revoke_supplier_portal_grant(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="Supplier representative changed",
        )
        self.assertEqual(revocation.pk, retry.pk)
        self.assertEqual(SupplierPortalGrantRevocation.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            get_supplier_portal_rfq_context(actor=self.external, grant=grant)
        with self.assertRaises(ValidationError):
            revocation.delete()


class SupplierPortalConcurrencyTests(SupplierPortalFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def test_concurrent_identical_submission_creates_one_receipt(self):
        _, _, grant = self._accepted_grant()
        barrier = Barrier(2)

        def submit_once() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                receipt = submit_supplier_portal_quote(
                    actor=User.objects.get(pk=self.external.pk),
                    grant=SupplierPortalGrant.objects.get(pk=grant.pk),
                    integrity_fingerprint="c" * 64,
                    idempotency_key="portal-concurrent",
                )
                return str(receipt.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            receipt_ids = list(pool.map(lambda _: submit_once(), range(2)))

        self.assertEqual(receipt_ids[0], receipt_ids[1])
        self.assertEqual(SupplierPortalSubmissionReceipt.objects.count(), 1)
