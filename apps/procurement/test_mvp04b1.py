"""RFQ preparation presentation and forged-input boundaries; existing services remain authoritative."""

from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import MembershipScopeGrant
from apps.projects.models import Project

from .models import PurchaseRequest, PurchaseRequestItem, RequestForQuotation
from .rfq_services import create_rfq, submit_rfq_for_issue
from .test_mvp04b_scope import CommercialScopeFixture


class RFQPreparationTests(CommercialScopeFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.login(self.owner)

    def endpoint(self, rfq, action="detail"):
        return reverse(f"procurement:rfq_{action}", args=[rfq.pk])

    def create_data(self, pr, number="PREP-01"):
        now = timezone.now() + timedelta(days=3)
        return {
            "purchase_request_id": str(pr.pk),
            "rfq_number": number,
            "title": "استعلام جدید مصالح",
            "closing_at": now.strftime("%Y-%m-%d %H:%M"),
            "earliest_opening_at": now.strftime("%Y-%m-%d %H:%M"),
            "terms": "شرایط حفظ‌شده",
        }

    def test_context_and_general_creation_keep_parent_and_validate_dates(self):
        rfq = self.draft_rfq(selected=0)
        pr = rfq.purchase_request
        create = reverse("procurement:rfq_create")
        response = self.client.get(create)
        self.assertEqual(
            response.context["form"]
            .fields["purchase_request_id"]
            .widget.attrs["data-business-choice"],
            "purchase_request_id",
        )
        contextual = create + f"?purchase_request={pr.pk}"
        self.assertTrue(
            self.client.get(contextual)
            .context["form"]
            .fields["purchase_request_id"]
            .widget.is_hidden
        )
        data = self.create_data(pr)
        response = self.client.post(contextual, data)
        self.assertEqual(response.status_code, 302)
        new = RequestForQuotation.objects.get(rfq_number="PREP-01")
        self.assertEqual(new.purchase_request_id, pr.pk)
        self.assertEqual(new.project_id, pr.project_id)
        self.assertFalse(new.lines.exists())
        self.assertFalse(new.scope_definitions.exists())
        data.update(rfq_number="BAD-DATE", earliest_opening_at="2020-01-01 10:00")
        response = self.client.post(create, data)
        self.assertContains(response, "شرایط حفظ‌شده", status_code=400)
        self.assertIn("earliest_opening_at", response.context["form"].errors)

    def test_forged_parent_line_supplier_and_internal_keys_fail_without_identifier_echo(
        self,
    ):
        rfq = self.draft_rfq(selected=0)
        create = (
            reverse("procurement:rfq_create")
            + f"?purchase_request={rfq.purchase_request_id}"
        )
        foreign_pr = PurchaseRequest.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            request_number="SECRET-PR",
            title="سرّی",
            status="draft",
            created_by=self.outsider,
        )
        data = self.create_data(foreign_pr)
        self.assertEqual(self.client.post(create, data).status_code, 400)
        self.assertFalse(
            RequestForQuotation.objects.filter(rfq_number="PREP-01").exists()
        )
        foreign_item = PurchaseRequestItem.objects.create(
            organization=self.other_organization,
            purchase_request=foreign_pr,
            material=self.other_material,
            unit_of_measure=self.other_unit,
            quantity=10,
            description="secret",
            created_by=self.outsider,
        )
        response = self.client.post(
            self.endpoint(rfq, "line_add"),
            {
                "purchase_request_item_id": foreign_item.pk,
                "quantity": "3",
                "description": "حفظ شرح",
            },
        )
        self.assertContains(response, "حفظ شرح", status_code=400)
        self.assertFalse(rfq.lines.exists())
        from .rfq_services import add_rfq_line

        add_rfq_line(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            purchase_request_item=self.source[0],
            quantity=5,
        )
        self.define(rfq)
        submit_rfq_for_issue(organization=self.organization, actor=self.owner, rfq=rfq)
        for identifier in (str(self.other_supplier.pk), str(uuid4()), "bad-identifier"):
            response = self.client.post(
                self.endpoint(rfq, "issue"),
                {"supplier_ids": [identifier], "idempotency_key": "retry"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(
                identifier,
                response.content.decode(),
                "forged identifier must not be echoed",
            )
        response = self.client.post(
            self.endpoint(rfq, "issue"), {"supplier_ids": [self.supplier.pk]}
        )
        self.assertContains(response, "اطلاعات فرم معتبر نیست", status_code=400)
        self.assertNotContains(response, "کلید یکتای", status_code=400)
        self.assertFalse(rfq.versions.exists())

    def test_forged_scope_unit_is_rejected_without_raw_uuid_error(self):
        rfq = self.draft_rfq()
        url = reverse("procurement:rfq_scope_define", args=[rfq.pk])
        form = self.client.get(url).context["form"]
        data = {
            name: form[name].value()
            for name in (
                "version_number",
                "expected_revision",
                "source_fingerprint",
                "idempotency_key",
            )
        }
        data.update(
            scope_type="lot",
            scope_code="بسته مصالح",
            member_0="5",
            required_quantity="1",
            unit_of_measure="malformed-unit",
            independently_awardable="yes",
            allows_split_award="no",
            allows_alternates="no",
            operation="append",
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(
            "malformed-unit",
            response.content.decode(),
            "invalid unit must not be echoed",
        )
        self.assertFalse(rfq.scope_definitions.exists())

    def test_line_selector_uses_source_and_excludes_already_selected(self):
        rfq = self.draft_rfq(items=2, selected=1)
        choices = (
            reverse("procurement:rfq_choices", args=["purchase_request_item_id"])
            + f"?rfq={rfq.pk}"
        )
        rows = self.client.get(choices).json()["results"]
        self.assertEqual([row["value"] for row in rows], [str(self.source[1].pk)])
        self.assertIn(self.source[1].material.name, rows[0]["label"])
        response = self.client.post(
            self.endpoint(rfq, "line_add"),
            {
                "purchase_request_item_id": self.source[1].pk,
                "quantity": 11,
                "description": "حفظ خطا",
            },
        )
        self.assertContains(response, "حفظ خطا", status_code=400)
        self.assertEqual(
            response.context["line_form"]["purchase_request_item_id"].value(),
            str(self.source[1].pk),
        )
        self.assertEqual(rfq.lines.count(), 1)

    def test_list_search_filters_sort_pagination_and_business_chips(self):
        rfq = self.draft_rfq()
        for i in range(27):
            create_rfq(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                purchase_request=rfq.purchase_request,
                rfq_number=f"LIST-{i:02d}",
                title=f"خرید {i}",
                closing_at=rfq.closing_at,
                earliest_opening_at=rfq.earliest_opening_at,
            )
        listing = reverse("procurement:rfq_list")
        response = self.client.get(
            listing,
            {
                "q": "LIST-",
                "status": "draft",
                "project": self.project.pk,
                "sort": "number",
                "direction": "asc",
                "page": 2,
            },
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 27)
        self.assertEqual(len(response.context["rfqs"]), 2)
        self.assertEqual(response.context["rfqs"][0].rfq_number, "LIST-25")
        self.assertEqual(response.context["filter_bar"]["active_count"], 3)
        response = self.client.get(listing, {"project": self.other_project.pk})
        self.assertFalse(response.context["rfqs"])
        response = self.client.get(listing, {"closing_from": "2099-01-01"})
        self.assertFalse(response.context["rfqs"])

    def test_action_flags_project_scope_and_unauthorized_direct_posts(self):
        rfq = self.draft_rfq()
        self.login(self.viewer)
        response = self.client.get(self.endpoint(rfq))
        self.assertEqual(response.status_code, 200)
        for flag in (
            "can_add_line",
            "can_submit",
            "can_issue",
            "can_cancel",
            "can_manage_scope",
        ):
            self.assertFalse(response.context[flag], flag)
        for action in ("line_add", "submit", "issue", "cancel"):
            self.assertIn(
                self.client.post(self.endpoint(rfq, action), {}).status_code, (403, 404)
            )
        self.login(self.owner)
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="UNRELATED", name="پروژه دیگر"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=project,
            reason="isolated fixture",
        )
        self.assertEqual(self.client.get(self.endpoint(rfq)).status_code, 404)
        self.assertEqual(
            self.client.post(self.endpoint(rfq, "issue"), {}).status_code, 404
        )
        self.assertFalse(
            self.client.get(
                reverse("procurement:rfq_choices", args=["purchase_request_id"])
            ).json()["results"]
        )

    def test_issue_freeze_supplier_error_retention_and_preparation_only_read_model(
        self,
    ):
        rfq = self.draft_rfq()
        self.define(rfq)
        submit_rfq_for_issue(organization=self.organization, actor=self.owner, rfq=rfq)
        response = self.client.post(
            self.endpoint(rfq, "issue"),
            {"supplier_ids": [self.supplier.pk], "idempotency_key": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            str(self.supplier.pk),
            response.context["issue_form"]["supplier_ids"].value(),
        )
        data = {"supplier_ids": [self.supplier.pk], "idempotency_key": "business-retry"}
        self.assertEqual(
            self.client.post(self.endpoint(rfq, "issue"), data).status_code, 302
        )
        self.assertEqual(
            self.client.post(self.endpoint(rfq, "issue"), data).status_code, 302
        )
        self.assertEqual(rfq.versions.count(), 1)
        response = self.client.get(self.endpoint(rfq))
        for flag in ("can_add_line", "can_submit", "can_issue"):
            self.assertFalse(response.context[flag])
        self.assertTrue(response.context["can_addendum"])
        self.assertContains(response, "دامنه تثبیت‌شده")
        self.assertContains(response, self.supplier.display_name)
        self.assertNotIn("quote_revisions", response.context)
        self.assertNotContains(response, "پیشنهادهای مهروموم‌شده")
        version = rfq.versions.get()
        self.assertEqual(version.commercial_scopes.get().required_quantity, 5)
        self.assertEqual(
            self.client.post(
                self.endpoint(rfq, "line_add"),
                {"purchase_request_item_id": self.source[0].pk, "quantity": 1},
            ).status_code,
            400,
        )
        version.refresh_from_db()
        self.assertEqual(version.lines.get().quantity, 10)
