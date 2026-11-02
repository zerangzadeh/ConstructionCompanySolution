"""MVP-04A PR HTTP journey and authority boundaries on isolated PostgreSQL."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.projects.models import Project

from .models import PurchaseRequest, RequestForQuotation
from .services import (
    add_purchase_request_item,
    create_purchase_request,
    submit_purchase_request,
)
from .tests import ProcurementFixtureMixin


class RequestJourneyFixture(ProcurementFixtureMixin):
    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def draft(self, number="PR-A"):
        return create_purchase_request(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            request_number=number,
            title="مصالح فونداسیون",
        )

    def submitted(self, number="PR-A"):
        record = self.draft(number)
        add_purchase_request_item(
            organization=self.organization,
            actor=self.member,
            purchase_request=record,
            material=self.material,
            quantity=Decimal("12.5"),
        )
        submit_purchase_request(
            organization=self.organization, actor=self.member, purchase_request=record
        )
        record.refresh_from_db()
        return record

    def url(self, record, action="detail"):
        return reverse(f"procurement:request_{action}", args=[record.pk])


class PurchaseRequestJourneyTests(RequestJourneyFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.login(self.owner)

    def test_existing_separation_rule_hides_decision_and_still_denies_post(self):
        from copy import deepcopy

        from apps.accounts.models import User
        from apps.organizations.models import MembershipRole, MembershipStatus
        from apps.workflows.services import (
            create_workflow_draft,
            edit_workflow_draft,
            publish_workflow_version,
        )

        from .workflow import COMPATIBILITY_CONFIGURATION, WORKFLOW_TYPE_CODE

        reviewer = User.objects.create_user(username="independent-reviewer")
        membership = self.organization.memberships.create(
            user=reviewer,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.establish_test_membership_authority(membership)
        configuration = deepcopy(COMPATIBILITY_CONFIGURATION)
        configuration["steps"][1]["configuration"]["exclude_creator"] = True
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=WORKFLOW_TYPE_CODE,
            code="mvp04a-separation",
            name="بررسی مستقل",
            scope={"project_id": str(self.project.pk)},
        )
        edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=configuration,
        )
        publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )
        record = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            request_number="SOD-UI",
            title="بررسی مستقل خرید",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.owner,
            purchase_request=record,
            material=self.material,
            quantity=Decimal(1),
        )
        submit_purchase_request(
            organization=self.organization, actor=self.owner, purchase_request=record
        )
        response = self.client.get(self.url(record))
        self.assertFalse(response.context["can_approve"])
        self.assertFalse(response.context["can_reject"])
        self.client.post(self.url(record, "approve"), {"reason": "تلاش غیرمجاز"})
        record.refresh_from_db()
        self.assertEqual(record.status, "submitted")

    def test_scoped_create_and_inline_item_retention_then_submit_approve_handoff(self):
        create = (
            reverse("procurement:request_create") + f"?project_id={self.project.pk}"
        )
        response = self.client.get(create)
        self.assertTrue(response.context["form"].fields["project"].widget.is_hidden)
        response = self.client.post(
            create,
            {
                "project": self.project.pk,
                "request_number": "PR-UI",
                "title": "نیاز خرید",
            },
        )
        record = PurchaseRequest.objects.get(request_number="PR-UI")
        self.assertRedirects(response, self.url(record))
        response = self.client.post(
            self.url(record, "item_add"),
            {
                "material": self.material.pk,
                "quantity": "-1",
                "description": "شرح حفظ‌شده",
            },
        )
        self.assertContains(response, "شرح حفظ‌شده", status_code=400)
        self.assertEqual(
            response.context["item_form"]["material"].value(), str(self.material.pk)
        )
        self.assertEqual(record.items.count(), 0)
        self.client.post(
            self.url(record, "item_add"),
            {"material": self.material.pk, "quantity": "2", "description": "مصرف"},
        )
        self.client.post(self.url(record, "submit"))
        response = self.client.get(self.url(record))
        self.assertTrue(response.context["can_approve"])
        self.assertTrue(response.context["can_reject"])
        self.assertFalse(response.context["can_add_item"])
        self.client.post(self.url(record, "approve"), {"approve-reason": "تأیید نیاز"})
        record.refresh_from_db()
        self.assertEqual(record.status, "approved")
        response = self.client.get(self.url(record))
        handoff = response.context["rfq_create_url"]
        self.assertTrue(handoff)
        response = self.client.get(handoff)
        self.assertTrue(
            response.context["form"].fields["purchase_request_id"].widget.is_hidden
        )
        when = timezone.now() + timedelta(days=3)
        payload = {
            "purchase_request_id": record.pk,
            "rfq_number": "RFQ-UI",
            "title": "استعلام نیاز",
            "closing_at": when,
            "earliest_opening_at": when,
        }
        response = self.client.post(handoff, payload)
        self.assertEqual(response.status_code, 302)
        rfq = RequestForQuotation.objects.get(rfq_number="RFQ-UI")
        self.assertEqual(rfq.purchase_request_id, record.pk)
        self.assertEqual(rfq.project_id, self.project.pk)

    def test_reject_cancel_errors_and_final_state_actions(self):
        record = self.submitted()
        response = self.client.post(self.url(record, "reject"), {"reject-reason": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context["open_action"], "reject")
        self.client.post(
            self.url(record, "reject"), {"reject-reason": "نیاز اصلاح شود"}
        )
        record.refresh_from_db()
        self.assertEqual(record.status, "rejected")
        response = self.client.get(self.url(record))
        self.assertContains(response, "نیاز اصلاح شود")
        self.assertFalse(response.context["can_submit"])
        self.assertFalse(response.context["can_cancel"])
        for candidate in (self.draft("PR-C"), self.submitted("PR-CS")):
            response = self.client.post(
                self.url(candidate, "cancel"), {"cancel-reason": ""}
            )
            self.assertEqual(response.status_code, 400)
            self.client.post(
                self.url(candidate, "cancel"), {"cancel-reason": "نیاز منتفی شد"}
            )
            candidate.refresh_from_db()
            self.assertEqual(candidate.status, "cancelled")

    def test_cross_tenant_create_material_detail_and_context_are_denied(self):
        record = self.draft()
        create = (
            reverse("procurement:request_create") + f"?project_id={self.project.pk}"
        )
        response = self.client.post(
            create,
            {
                "project": self.other_project.pk,
                "request_number": "FORGED",
                "title": "forged",
            },
        )
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(
            PurchaseRequest.objects.filter(request_number="FORGED").exists()
        )
        response = self.client.post(
            self.url(record, "item_add"),
            {"material": self.other_material.pk, "quantity": "1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(record.items.exists())
        for route in ("request_create", "request_list"):
            self.assertEqual(
                self.client.get(
                    reverse(f"procurement:{route}")
                    + f"?project_id={self.other_project.pk}"
                ).status_code,
                404,
            )
        self.login(self.outsider)
        session = self.client.session
        set_active_organization(session, self.other_organization)
        session.save()
        self.assertEqual(self.client.get(self.url(record)).status_code, 404)

    def test_unauthorized_and_wrong_project_actions_and_choices(self):
        record = self.submitted()
        self.login(self.viewer)
        response = self.client.get(self.url(record))
        self.assertFalse(response.context["can_approve"])
        self.assertFalse(response.context["can_reject"])
        self.assertEqual(
            self.client.post(
                self.url(record, "approve"), {"reason": "forged"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("procurement:request_create")).status_code, 403
        )
        self.login(self.member)
        membership = self.organization.memberships.get(user=self.member)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        allowed = Project.objects.create(
            organization=self.organization, name="پروژه مجاز", code="ALLOW"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=allowed,
            reason="test",
            source="test_fixture",
        )
        self.assertEqual(self.client.get(self.url(record)).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.url(record, "approve"), {"reason": "forged"}
            ).status_code,
            403,
        )
        response = self.client.get(
            reverse("procurement:request_choices", args=["project"])
        )
        self.assertEqual(
            [row["value"] for row in response.json()["results"]], [str(allowed.pk)]
        )

    def test_rfqs_reject_forged_context_and_unapproved_pr(self):
        record, _ = self.create_approved_request()
        other, _ = self.create_approved_request_for_test()
        entry = reverse("procurement:rfq_create") + f"?purchase_request={record.pk}"
        response = self.client.post(
            entry,
            {"purchase_request_id": other.pk, "rfq_number": "FORGED", "title": "bad"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("purchase_request_id", response.context["form"].errors)
        draft = self.draft("UNAPPROVED")
        self.assertEqual(
            self.client.get(
                reverse("procurement:rfq_create") + f"?purchase_request={draft.pk}"
            ).status_code,
            404,
        )
        self.assertFalse(RequestForQuotation.objects.exists())

    def create_approved_request_for_test(self):
        from .services import approve_purchase_request

        record = self.submitted("PR-SECOND")
        approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=record,
            reason="ok",
        )
        return record, record.items.first()

    def test_list_search_filters_sorting_pagination_and_project_context(self):
        PurchaseRequest.objects.bulk_create(
            [
                PurchaseRequest(
                    organization=self.organization,
                    project=self.project,
                    request_number=f"LIST-{i:02}",
                    title="مصالح آزمایشی",
                )
                for i in range(28)
            ]
        )
        listing = reverse("procurement:request_list")
        response = self.client.get(
            listing,
            {
                "project_id": self.project.pk,
                "q": "LIST",
                "status": "draft",
                "sort": "number",
                "direction": "asc",
                "page": "2",
            },
        )
        self.assertEqual(len(response.context["requests"]), 3)
        self.assertEqual(response.context["requests"][0].request_number, "LIST-25")
        self.assertEqual(response.context["filter_bar"]["result_count"], 28)
        self.assertNotIn("project", response.context["filter_bar"]["form"].fields)
        self.assertContains(response, "درخواست خرید جدید")
        self.assertEqual(
            self.client.get(listing, {"status": "injected"}).context["filter_bar"][
                "result_count"
            ],
            0,
        )
