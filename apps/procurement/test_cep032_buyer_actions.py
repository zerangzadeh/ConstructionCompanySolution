"""Real buyer UI commands, separation, confidentiality and relation-boundary tests."""

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.organizations.services import set_active_organization
from apps.procurement import models as m
from apps.procurement.opening_services import revoke_quote_confidential_access
from apps.procurement.rfq_services import (
    add_rfq_line,
    create_rfq,
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.test_p5_s11_comparison_award import P5S11FixtureMixin


class BuyerActionTests(P5S11FixtureMixin, TestCase):
    """Current effective grants exist only in this new isolated fixture."""

    def _effective_actor(self, user):
        membership = self.organization.memberships.get(user=user)
        role = OrganizationRole.objects.create(
            code=f"cep032-{user.pk}", name="Buyer test"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(code__startswith="rfq").union(
                BusinessPermission.objects.filter(code__startswith="purchase_request")
            )
        )
        membership.role_definition = role
        membership.save(update_fields=["role_definition"])
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-032 isolated test scope",
        )

    def create_approved_request(self, quantity=Decimal("10.0000")):
        for user in (self.owner, self.member):
            self._effective_actor(user)
        # Fixture source, not a re-test/repair of the unrelated purchase workflow.
        from django.utils import timezone

        source = m.PurchaseRequest.objects.create(
            organization=self.organization,
            project=self.project,
            request_number="CEP032-SOURCE",
            title="Approved fixture source",
            created_by=self.member,
        )
        item = m.PurchaseRequestItem.objects.create(
            organization=self.organization,
            purchase_request=source,
            material=self.material,
            unit_of_measure=self.unit,
            description="Source material",
            quantity=quantity,
            created_by=self.member,
        )
        m.PurchaseRequest.objects.filter(pk=source.pk).update(
            status="approved", approved_by=self.owner, approved_at=timezone.now()
        )
        source.refresh_from_db()
        return source, item

    def _make_actor(self, username):
        user = super()._make_actor(username)
        self._effective_actor(user)
        return user

    def login(self, user=None, *, other=False, client=None):
        client = client or self.client
        client.force_login(user or self.preparer)
        session = client.session
        set_active_organization(
            session, self.other_organization if other else self.organization
        )
        session.save()

    @property
    def rfq(self):
        return self.revision.envelope.rfq

    def action(self, code, data, *, rfq=None):
        return self.client.post(
            reverse("procurement:rfq_buyer_action", args=[(rfq or self.rfq).pk, code]),
            data,
        )

    def comparison_data(self, key="ui-comparison"):
        return {
            "scope": self.scope.pk,
            "idempotency_key": key,
            "rows-TOTAL_FORMS": "1",
            "rows-INITIAL_FORMS": "0",
            "rows-0-quote_revision_id": self.revision.pk,
            "rows-0-offered_quantity": "10",
            "rows-0-unit_price": "12.50",
            "rows-0-currency": "IRR",
            "rows-0-explicit_discount": "0.50",
            "rows-0-source_locator": "supplier-original-page-1",
        }

    def prepare_evaluate(self, key="ui-comparison"):
        self.login()
        response = self.action("prepare_comparison", self.comparison_data(key))
        self.assertEqual(response.status_code, 302, response.content[:1000])
        comparison = m.CommercialComparison.objects.get(idempotency_key=key)
        self.assertEqual(
            self.action(
                "appoint_evaluator",
                {
                    "comparison": comparison.pk,
                    "membership": self.organization.memberships.get(
                        user=self.preparer
                    ).pk,
                },
            ).status_code,
            302,
        )
        appointment = comparison.evaluator_appointments.get()
        self.assertEqual(
            self.action(
                "evaluate",
                {
                    "appointment": appointment.pk,
                    "input": comparison.inputs.get().pk,
                    "recommendation": "documented commercial review",
                    "evidence": "review-1",
                },
            ).status_code,
            302,
        )
        return comparison

    def test_comparison_award_flow_preserves_separation_history_and_no_downstream(self):
        comparison = self.prepare_evaluate()
        self.assertEqual(
            self.action(
                "finalize_comparison", {"comparison": comparison.pk, "reason": "ready"}
            ).status_code,
            400,
        )
        self.assertFalse(comparison.superseded_by.exists())
        self.login(self.approver)
        self.assertEqual(
            self.action(
                "finalize_comparison",
                {"comparison": comparison.pk, "reason": "independent check"},
            ).status_code,
            302,
        )
        finalized = comparison.superseded_by.get()
        self.assertIsNotNone(finalized.finalized_at)
        comparison.refresh_from_db()
        self.assertIsNone(comparison.finalized_at)
        self.login()
        payload = {
            "comparison": finalized.pk,
            "outcome": "awarded",
            "reason": "documented buyer choice",
            "evidence": "decision-note",
            "idempotency_key": "ui-award",
            "rows-TOTAL_FORMS": "1",
            "rows-INITIAL_FORMS": "0",
            "rows-0-comparison_input_id": finalized.inputs.get().pk,
            "rows-0-quantity": "5",
        }
        self.assertEqual(self.action("prepare_award", payload).status_code, 302)
        preparation = m.SourcingAwardPreparation.objects.get(idempotency_key="ui-award")
        self.assertEqual(
            self.action("finalize_award", {"preparation": preparation.pk}).status_code,
            400,
        )
        self.assertFalse(m.SourcingAward.objects.exists())
        self.login(self.approver)
        for _ in range(2):
            self.assertEqual(
                self.action(
                    "finalize_award", {"preparation": preparation.pk}
                ).status_code,
                302,
            )
        award = m.SourcingAward.objects.get()
        self.assertEqual(award.allocations.get().quantity, Decimal(5))
        self.assertEqual(award.unawarded_quantity, Decimal(5))
        history = self.client.get(
            reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        )
        self.assertContains(history, "تصمیم نهایی")
        self.assertContains(history, "decision-note")
        self.assertEqual(self.organization.purchase_orders.count(), 0)
        from apps.accounting.models import JournalEntry
        from apps.contracts.models import Contract
        from apps.projects.models import ProjectCostFact
        from apps.subledgers.models import Obligation
        from apps.treasury.models import TreasuryMovement

        for model in (
            JournalEntry,
            Contract,
            ProjectCostFact,
            Obligation,
            TreasuryMovement,
        ):
            self.assertFalse(
                model.objects.filter(organization=self.organization).exists()
            )

    def test_quote_capture_submit_withdraw_retry_and_foreign_rfq_rejected(self):
        source = self.rfq.purchase_request
        rfq = create_rfq(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            purchase_request=source,
            rfq_number="UI-QUOTE",
            title="UI quote",
            closing_at=self.revision.rfq_version.closing_at,
            earliest_opening_at=self.revision.rfq_version.earliest_opening_at,
        )
        add_rfq_line(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            purchase_request_item=source.items.get(),
            quantity=Decimal(2),
        )
        submit_rfq_for_issue(organization=self.organization, actor=self.owner, rfq=rfq)
        version = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="ui-issue",
        )
        rfq.refresh_from_db()
        self.login(self.owner)
        payload = {
            "invitation": version.invitations.get().pk,
            "integrity_fingerprint": "a" * 64,
            "source_channel": "manual_capture",
            "idempotency_key": "ui-capture",
        }
        for _ in range(2):
            self.assertEqual(self.action("capture", payload, rfq=rfq).status_code, 302)
        revision = m.QuoteRevision.objects.get(envelope__rfq=rfq)
        self.assertEqual(
            self.action(
                "submit",
                {"quote_revision": self.revision.pk, "idempotency_key": "forged"},
                rfq=rfq,
            ).status_code,
            400,
        )
        self.assertEqual(
            self.action(
                "submit",
                {"quote_revision": revision.pk, "idempotency_key": "ui-submit"},
                rfq=rfq,
            ).status_code,
            302,
        )
        self.assertEqual(
            self.action(
                "withdraw",
                {"quote_revision": revision.pk, "idempotency_key": "ui-withdraw"},
                rfq=rfq,
            ).status_code,
            302,
        )
        revision.refresh_from_db()
        self.assertEqual(revision.status, "withdrawn")

    def test_revoked_confidential_grant_hides_values_and_rejects_assertions(self):
        comparison = self.prepare_evaluate()
        url = reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        self.assertContains(self.client.get(url), "supplier-original-page-1")
        grant = m.QuoteConfidentialAccessGrant.objects.get(
            quote_revision=self.revision, membership__user=self.preparer
        )
        revoke_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="access ended",
        )
        self.assertNotContains(self.client.get(url), "supplier-original-page-1")
        self.assertEqual(
            self.action(
                "prepare_comparison", self.comparison_data("denied")
            ).status_code,
            400,
        )
        self.assertEqual(m.CommercialComparison.objects.count(), 1)
        self.assertEqual(comparison.inputs.count(), 1)

    def test_permission_tenant_csrf_and_get_do_not_mutate(self):
        self.login(self.viewer)
        self.assertIn(
            self.action("prepare_comparison", self.comparison_data()).status_code,
            (302, 403),
        )
        self.login(self.outsider, other=True)
        membership = self.other_organization.memberships.get(user=self.outsider)
        role = OrganizationRole.objects.create(
            code="cep032-other-buyer", name="Other buyer"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=["rfqs.view", "rfq_quotes.prepare_comparison"]
            )
        )
        membership.role_definition = role
        membership.save(update_fields=["role_definition"])
        MembershipScopeGrant.objects.create(
            organization=self.other_organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Other test tenant",
        )
        self.assertEqual(
            self.action("prepare_comparison", self.comparison_data()).status_code, 404
        )
        self.login()
        before = m.CommercialComparison.objects.count()
        url = reverse(
            "procurement:rfq_buyer_action", args=[self.rfq.pk, "prepare_comparison"]
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(m.CommercialComparison.objects.count(), before)

        csrf_client = Client(enforce_csrf_checks=True)
        self.login(client=csrf_client)
        self.assertEqual(csrf_client.post(url, self.comparison_data()).status_code, 403)
        self.assertEqual(m.CommercialComparison.objects.count(), before)

    def test_authorized_action_forms_render_without_mutating_sources(self):
        from apps.procurement.rfq_action_forms import ACTIONS

        self.prepare_evaluate()
        before = m.CommercialComparison.objects.count()
        for action in ACTIONS:
            with self.subTest(action=action):
                response = self.client.get(
                    reverse("procurement:rfq_buyer_action", args=[self.rfq.pk, action])
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "فقط منابع مجاز همین استعلام")
        self.assertEqual(m.CommercialComparison.objects.count(), before)

    def test_explicit_no_award_and_cross_comparison_allocation_rejection(self):
        comparisons = [self.prepare_evaluate(key) for key in ("first", "second")]
        finalized = []
        self.login(self.approver)
        for comparison in comparisons:
            self.assertEqual(
                self.action(
                    "finalize_comparison",
                    {"comparison": comparison.pk, "reason": "independent"},
                ).status_code,
                302,
            )
            finalized.append(comparison.superseded_by.get())
        self.login()
        data = {
            "comparison": finalized[0].pk,
            "outcome": "awarded",
            "reason": "explicit",
            "evidence": "note",
            "idempotency_key": "mismatch",
            "rows-TOTAL_FORMS": "1",
            "rows-INITIAL_FORMS": "0",
            "rows-0-comparison_input_id": finalized[1].inputs.get().pk,
            "rows-0-quantity": "1",
        }
        self.assertEqual(self.action("prepare_award", data).status_code, 400)
        self.assertFalse(m.SourcingAwardPreparation.objects.exists())
        data.update(outcome="no_award", idempotency_key="no-award")
        data.pop("rows-0-comparison_input_id")
        data.pop("rows-0-quantity")
        self.assertEqual(self.action("prepare_award", data).status_code, 302)
        preparation = m.SourcingAwardPreparation.objects.get()
        self.assertFalse(preparation.allocations.exists())
        self.login(self.approver)
        self.assertEqual(
            self.action("finalize_award", {"preparation": preparation.pk}).status_code,
            302,
        )
        self.assertEqual(m.SourcingAward.objects.get().outcome, "no_award")

    def test_opening_and_admissibility_actions_retain_independent_decisions(self):
        self.login(self.owner)
        opening_request = self.revision.opening_requests.get()
        self.assertEqual(
            self.action(
                "approve_opening", {"opening_request": opening_request.pk}
            ).status_code,
            400,
        )
        self.assertEqual(m.QuoteOpeningEvent.objects.count(), 1)
        self.login()
        payload = {
            "quote_revision": self.revision.pk,
            "state": "admissible",
            "reason_code": "requirements_met",
            "rationale": "independent corrected evidence",
            "idempotency_key": "ui-admissibility",
        }
        self.assertEqual(self.action("prepare_admissibility", payload).status_code, 302)
        preparation = m.QuoteAdmissibilityPreparation.objects.get(
            idempotency_key="ui-admissibility"
        )
        approval = {"preparation": preparation.pk, "supersedes": self.decision.pk}
        self.assertEqual(
            self.action("approve_admissibility", approval).status_code, 400
        )
        self.login(self.approver)
        self.assertEqual(
            self.action("approve_admissibility", approval).status_code, 302
        )
        self.assertEqual(m.QuoteAdmissibilityDecision.objects.count(), 2)
        self.assertEqual(self.decision.superseded_by.count(), 1)

    def test_conflict_blocks_evaluation_and_requires_independent_disposition(self):
        comparison = self.prepare_evaluate()
        appointment = comparison.evaluator_appointments.get()
        self.assertEqual(
            self.action(
                "declare_conflict",
                {"appointment": appointment.pk, "evidence": "declared relationship"},
            ).status_code,
            302,
        )
        conflict = appointment.conflicts.get()
        self.assertEqual(
            self.action(
                "evaluate",
                {
                    "appointment": appointment.pk,
                    "input": comparison.inputs.get().pk,
                    "recommendation": "denied",
                    "evidence": "denied",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.action(
                "dispose_conflict",
                {
                    "conflict": conflict.pk,
                    "approved": "yes",
                    "reason": "self disposition",
                },
            ).status_code,
            400,
        )
        self.login(self.approver)
        self.assertEqual(
            self.action(
                "dispose_conflict",
                {
                    "conflict": conflict.pk,
                    "approved": "yes",
                    "reason": "independent disposition",
                },
            ).status_code,
            302,
        )
        self.assertEqual(m.EvaluatorConflictDeclaration.objects.count(), 2)
