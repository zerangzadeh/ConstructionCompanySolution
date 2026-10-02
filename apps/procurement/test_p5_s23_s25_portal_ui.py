from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import BusinessPermissionCode
from apps.organizations.services import set_active_organization
from apps.procurement.models import PurchaseOrder, SupplierPortalSubmissionReceipt
from apps.procurement.portal_services import create_supplier_portal_invitation
from apps.procurement.test_p5_s08_sealed_custody import SealedCustodyFixtureMixin
from apps.procurement.test_p5_s18_s22_supplier_portal import SupplierPortalFixtureMixin


class SupplierPortalUiTests(
    SupplierPortalFixtureMixin, SealedCustodyFixtureMixin, TestCase
):
    def _client_for(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        return client

    def _internal_client(self):
        self._grant_internal_management()
        client = self._client_for(self.owner)
        set_active_organization(client.session, self.organization)
        client.session.save()
        return client

    def _portal_invitation(self):
        self._grant_internal_management()
        invitation, token = create_supplier_portal_invitation(
            organization=self.organization,
            actor=self.owner,
            rfq_invitation=self._issued_invitation(),
            invited_email=self.external.email,
            expires_at=timezone.now() + timedelta(days=1),
        )
        return invitation, token

    def test_acceptance_is_csrf_protected_and_replay_is_denied(self):
        invitation, token = self._portal_invitation()
        client = self._client_for(self.external)
        url = reverse("procurement:portal_accept")
        self.assertContains(client.get(url), "پذیرش دعوت‌نامه")
        self.assertEqual(client.post(url, {"token": token}).status_code, 403)
        client.get(url)
        response = client.post(
            url, {"token": token}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
        self.assertEqual(response.status_code, 302)
        replay = client.post(
            url, {"token": token}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
        self.assertEqual(replay.status_code, 302)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted")

    def test_external_context_is_exact_scope_and_submission_is_idempotent(self):
        invitation, token = self._portal_invitation()
        client = self._client_for(self.external)
        accept_url = reverse("procurement:portal_accept")
        client.get(accept_url)
        accepted = client.post(
            accept_url,
            {"token": token},
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        context_url = accepted.url
        context_response = client.get(context_url)
        self.assertContains(
            context_response,
            invitation.rfq_invitation.rfq_version.rfq.rfq_number,
        )
        self.assertNotContains(context_response, "یادداشت داخلی")
        self.assertContains(context_response, 'name="idempotency_key"', html=False)
        self.assertNotContains(context_response, "کلید یکتای ارسال")
        self.assertIn("no-cache", context_response.headers["Cache-Control"])
        submit_url = context_url + "submit/"
        payload = {
            "integrity_fingerprint": "a" * 64,
            "source_reference": "SUP-1",
            "idempotency_key": "ui-submit-1",
        }
        before_orders = PurchaseOrder.objects.count()
        client.get(context_url)
        first = client.post(
            submit_url, payload, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
        self.assertEqual(first.status_code, 302)
        second = client.post(
            submit_url, payload, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
        self.assertEqual(second.status_code, 302)
        self.assertEqual(SupplierPortalSubmissionReceipt.objects.count(), 1)
        self.assertEqual(PurchaseOrder.objects.count(), before_orders)
        self.assertEqual(client.post(context_url + "withdraw/").status_code, 404)

    def test_revoked_or_expired_grant_cannot_read_or_submit(self):
        _, _, grant = self._accepted_grant()
        grant.portal_invitation.__class__.objects.filter(
            pk=grant.portal_invitation_id
        ).update(expires_at=timezone.now() - timedelta(seconds=1))
        client = self._client_for(self.external)
        self.assertEqual(
            client.get(
                reverse("procurement:portal_context", args=[grant.pk])
            ).status_code,
            404,
        )

    def test_internal_management_requires_scope_and_is_csrf_protected(self):
        invitation = self._issued_invitation()
        client = self._client_for(self.owner)
        set_active_organization(client.session, self.organization)
        client.session.save()
        url = reverse("procurement:portal_invitation_manage", args=[invitation.pk])
        self.assertEqual(client.get(url).status_code, 403)
        client = self._internal_client()
        self.assertEqual(
            client.post(url, {"invited_email": self.external.email}).status_code, 403
        )

    def test_sealed_evidence_route_denies_cross_tenant_and_ungranted_access(self):
        revision, _ = self._closed_revision()
        client = self._client_for(self.owner)
        set_active_organization(client.session, self.organization)
        client.session.save()
        url = reverse("procurement:sealed_evidence_custody", args=[revision.pk])
        self.assertEqual(client.get(url).status_code, 403)
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        self.assertEqual(client.get(url).status_code, 200)
        accepted = client.post(
            url,
            {
                "evidence_type": "supplier_original",
                "evidence_slot": "",
                "upload": SimpleUploadedFile(
                    "supplier.pdf",
                    b"%PDF-1.7\nsealed\n%%EOF",
                    content_type="application/pdf",
                ),
                "idempotency_key": "ui-custody-1",
                "expected_sha256": "",
            },
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(accepted.status_code, 302)
        other_client = self._client_for(self.outsider)
        set_active_organization(other_client.session, self.other_organization)
        other_client.session.save()
        self.assertEqual(other_client.get(url).status_code, 404)
