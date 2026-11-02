"""Buyer journey UI boundaries; governed domain fixtures remain authoritative."""

import hashlib
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.organizations.services import set_active_organization
from apps.procurement import models as m
from apps.procurement.opening_services import revoke_quote_confidential_access
from apps.procurement.test_mvp04b_scope import CommercialScopeFixture
from apps.procurement.test_p5_s08_sealed_custody import _pdf_upload
from apps.procurement.test_p5_s11_comparison_award import P5S11FixtureMixin


class BuyerHTTPMixin:
    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def url(self, action, **context):
        from apps.procurement.buyer_ui import action_url

        return action_url(self.rfq, action, **context)

    def post(self, actor, action, data, **context):
        self.login(actor)
        return self.client.post(self.url(action, **context), data)


class QuoteReceiptJourneyTests(BuyerHTTPMixin, CommercialScopeFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.rfq = self.draft_rfq()
        self.define(self.rfq)
        self.version = self.issue(self.rfq)
        self.rfq.refresh_from_db()
        self.invitation = self.version.invitations.get()

    def capture(self, key="receipt", **changes):
        return self.post(
            self.owner,
            "capture",
            {
                "invitation": self.invitation.pk,
                "source_file": _pdf_upload(),
                "source_channel": "manual_capture",
                "idempotency_key": key,
                **changes,
            },
            invitation=self.invitation.pk,
        )

    def test_real_source_receipt_retry_revisions_submit_supersede_withdraw(self):
        response = self.capture()
        self.assertEqual(
            response.status_code,
            302,
            response.context["form"].errors if response.status_code == 400 else "",
        )
        first = m.QuoteRevision.objects.get()
        self.assertEqual(
            first.integrity_fingerprint,
            hashlib.sha256(_pdf_upload().read()).hexdigest(),
        )
        self.assertFalse(first.evidence_items.exists())
        self.assertEqual(self.capture().status_code, 302)
        self.assertEqual(m.QuoteRevision.objects.count(), 1)
        for revision in [first]:
            self.assertEqual(
                self.post(
                    self.owner,
                    "submit",
                    {"quote_revision": revision.pk, "idempotency_key": uuid4().hex},
                    quote_revision=revision.pk,
                ).status_code,
                302,
            )
        self.assertEqual(self.capture("correction").status_code, 302)
        second = m.QuoteRevision.objects.get(revision_number=2)
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertEqual(
            self.post(
                self.owner,
                "submit",
                {"quote_revision": second.pk, "idempotency_key": uuid4().hex},
                quote_revision=second.pk,
            ).status_code,
            302,
        )
        first.refresh_from_db()
        self.assertEqual(first.status, "superseded")
        self.assertEqual(
            self.post(
                self.owner,
                "withdraw",
                {"quote_revision": second.pk, "idempotency_key": uuid4().hex},
                quote_revision=second.pk,
            ).status_code,
            302,
        )
        second.refresh_from_db()
        self.assertEqual(second.status, "withdrawn")
        self.assertEqual(first.source_reference, "")

    def test_no_manual_technical_inputs_invalid_upload_and_cross_context_fail_closed(
        self,
    ):
        self.login(self.owner)
        response = self.client.get(self.url("capture", invitation=self.invitation.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("integrity_fingerprint", response.context["form"].fields)
        self.assertTrue(response.context["form"]["idempotency_key"].is_hidden)
        self.assertTrue(response.context["form"]["invitation"].is_hidden)
        response = self.capture(source_file=_pdf_upload(content=b"invalid"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(m.QuoteRevision.objects.exists())
        response = self.client.get(self.url("capture", invitation=uuid4()))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(m.QuoteRevision.objects.exists())


class SourcingWorkspaceJourneyTests(BuyerHTTPMixin, P5S11FixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.rfq = self.revision.envelope.rfq

    def test_exact_context_revocation_retry_preserves_one_auditable_revocation(self):
        grant = m.QuoteConfidentialAccessGrant.objects.get(
            quote_revision=self.revision, membership__user=self.preparer
        )
        for _ in range(2):
            response = self.post(
                self.owner,
                "revoke_access",
                {"grant": grant.pk, "reason": "پایان بررسی"},
                grant=grant.pk,
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(
            m.QuoteConfidentialAccessRevocation.objects.filter(grant=grant).count(), 1
        )

    def test_compatibility_custody_form_has_no_manual_technical_fields_and_scopes_get(
        self,
    ):
        from django.utils import timezone

        from apps.organizations.models import MembershipScopeGrant
        from apps.projects.models import Project

        self.login(self.owner)
        url = reverse("procurement:sealed_evidence_custody", args=[self.revision.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [field.name for field in response.context["form"].visible_fields()],
            ["evidence_type", "upload"],
        )
        self.assertNotContains(response, "SHA-256")
        self.assertIn("no-store", response["Cache-Control"])
        member = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="LIMIT", name="Limited"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=project,
            reason="test",
        )
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_workspace_real_values_active_grants_document_delivery_and_revocation(self):
        self._comparison()
        self.login(self.preparer)
        workspace = reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        response = self.client.get(workspace)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "هم‌مبناشده توسط سامانه")
        self.assertContains(response, "page-1-line-1")
        self.assertIn("no-store", response["Cache-Control"])
        document = reverse(
            "procurement:rfq_buyer_document", args=[self.rfq.pk, self.evidence.pk]
        )
        response = self.client.get(document)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        grant = m.QuoteConfidentialAccessGrant.objects.get(
            quote_revision=self.revision, membership__user=self.preparer
        )
        revoke_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="review ended",
        )
        response = self.client.get(workspace)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "page-1-line-1")
        self.assertFalse(response.context["comparisons"])
        self.assertEqual(self.client.get(document).status_code, 403)
        self.assertIn("no-store", self.client.get(workspace)["Cache-Control"])
        self.login(self.outsider)
        self.assertIn(self.client.get(workspace).status_code, (403, 404))

    def test_comparison_to_partial_award_lineage_and_no_award(self):
        comparison, _appointment = self._evaluated_comparison()
        result = self.post(
            self.approver,
            "finalize_comparison",
            {"comparison": comparison.pk, "reason": "بررسی کامل"},
            comparison=comparison.pk,
        )
        self.assertEqual(result.status_code, 302)
        finalized = m.CommercialComparison.objects.get(
            supersedes=comparison, finalized_at__isnull=False
        )
        row = finalized.inputs.get()
        payload = {
            "comparison": finalized.pk,
            "outcome": "awarded",
            "reason": "خرید مرحله اول",
            "evidence": "صورت‌جلسه خرید",
            "idempotency_key": "award-ui",
            "rows-TOTAL_FORMS": "1",
            "rows-INITIAL_FORMS": "0",
            "rows-0-comparison_input_id": row.pk,
            "rows-0-quantity": "4",
        }
        result = self.post(
            self.preparer, "prepare_award", payload, comparison=finalized.pk
        )
        self.assertEqual(result.status_code, 302, result.content.decode()[:1000])
        prep = m.SourcingAwardPreparation.objects.get()
        denied = self.post(
            self.preparer,
            "finalize_award",
            {"preparation": prep.pk},
            preparation=prep.pk,
        )
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(m.SourcingAward.objects.exists())
        self.assertEqual(
            self.post(
                self.approver,
                "finalize_award",
                {"preparation": prep.pk},
                preparation=prep.pk,
            ).status_code,
            302,
        )
        award = m.SourcingAward.objects.get()
        self.assertEqual(award.allocations.get().quote_revision_id, self.revision.pk)
        self.assertEqual(award.comparison_id, finalized.pk)
        self.assertEqual(
            award.unawarded_quantity, self.scope.required_quantity - Decimal(4)
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())
        no_award_payload = {
            **payload,
            "outcome": "no_award",
            "idempotency_key": "no-award-ui",
            "rows-TOTAL_FORMS": "0",
        }
        self.assertEqual(
            self.post(
                self.preparer,
                "prepare_award",
                no_award_payload,
                comparison=finalized.pk,
            ).status_code,
            302,
        )
        no_award = m.SourcingAwardPreparation.objects.get(outcome="no_award")
        result = self.post(
            self.approver,
            "finalize_award",
            {"preparation": no_award.pk, "supersedes": award.pk},
            preparation=no_award.pk,
        )
        self.assertEqual(result.status_code, 302)
        self.assertFalse(
            m.SourcingAward.objects.get(preparation=no_award).allocations.exists()
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())
        response = self.client.get(
            reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        )
        self.assertContains(response, "تصمیم پیشین محفوظ")
        self.assertNotContains(response, "مرحله بعد: سفارش خرید")

    def test_preopening_denial_and_no_commercial_content_without_grant(self):
        comparison = self._comparison()
        self.login(self.owner)
        response = self.client.get(
            reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "page-1-line-1")
        self.assertNotContains(
            response, comparison.inputs.get().assertion.source_locator
        )

    def test_award_input_cannot_cross_comparison_and_context_is_revalidated(self):
        from apps.procurement.comparison_services import finalize_comparison

        comparison, _ = self._evaluated_comparison()
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="complete",
        )
        other = self._comparison(key="other")
        result = self.post(
            self.preparer,
            "prepare_award",
            {
                "comparison": finalized.pk,
                "outcome": "awarded",
                "reason": "test",
                "evidence": "evidence",
                "idempotency_key": "invalid",
                "rows-TOTAL_FORMS": "1",
                "rows-INITIAL_FORMS": "0",
                "rows-0-comparison_input_id": other.inputs.get().pk,
                "rows-0-quantity": "1",
            },
            comparison=finalized.pk,
        )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(m.SourcingAwardPreparation.objects.exists())
