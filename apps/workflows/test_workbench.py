from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import BusinessPermission, BusinessPermissionCode
from apps.organizations.services import set_active_organization
from apps.procurement.models import PurchaseRequestStatus
from apps.procurement.services import (
    add_purchase_request_item,
    create_purchase_request,
    submit_purchase_request,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.projects.models import ProjectSite
from apps.workforce.models import Employee, EmployeePositionAssignment, Position

from .models import WorkItem, WorkItemStatus


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkbenchTests(ProcurementFixtureMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

    def _submitted_request(self, number: str):
        purchase_request = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            request_number=number,
            title=f"Workbench {number}",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.owner,
            purchase_request=purchase_request,
            material=self.material,
            quantity=Decimal(1),
        )
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=purchase_request,
        )
        return purchase_request

    def _item(self, purchase_request) -> WorkItem:
        return WorkItem.objects.get(
            organization=self.organization,
            instance__subject_id=purchase_request.pk,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        )

    def test_tenant_isolation_permissions_and_secure_source_link(self) -> None:
        own_request = self._submitted_request("WB-OWN")
        foreign_request = create_purchase_request(
            organization=self.other_organization,
            actor=self.outsider,
            project=self.other_project,
            request_number="WB-FOREIGN",
            title="Foreign work item",
        )
        add_purchase_request_item(
            organization=self.other_organization,
            actor=self.outsider,
            purchase_request=foreign_request,
            material=self.other_material,
            quantity=Decimal(1),
        )
        submit_purchase_request(
            organization=self.other_organization,
            actor=self.outsider,
            purchase_request=foreign_request,
        )

        response = self.client.get(reverse("workflows:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_request.title)
        self.assertContains(
            response,
            reverse(
                "procurement:request_detail", kwargs={"request_id": own_request.pk}
            ),
        )
        self.assertNotContains(response, foreign_request.title)

        viewer_role = self.organization.memberships.get(
            user=self.viewer
        ).role_definition
        viewer_role.permissions.remove(
            BusinessPermission.objects.get(code=BusinessPermissionCode.WORK_ITEMS_VIEW)
        )
        self.client.force_login(self.viewer)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()
        self.assertEqual(
            self.client.get(reverse("workflows:workbench")).status_code, 403
        )

    def test_multi_position_dedup_counts_states_and_filters(self) -> None:
        purchase_request = self._submitted_request("WB-FILTER")
        item = self._item(purchase_request)
        employee = Employee.objects.create(
            organization=self.organization,
            user=self.owner,
            employee_number="WB-OWNER",
            first_name="Work",
            last_name="Bench",
        )
        positions = [
            Position.objects.create(
                organization=self.organization, code=f"WB-{index}", title=title
            )
            for index, title in enumerate(("مدیر پروژه", "سرپرست کارگاه"), start=1)
        ]
        assignments = [
            EmployeePositionAssignment.objects.create(
                organization=self.organization,
                employee=employee,
                position=position,
                start_date=timezone.localdate() - timedelta(days=1),
                is_primary=index == 0,
            )
            for index, position in enumerate(positions)
        ]
        candidate = item.candidates.get(
            membership=self.organization.memberships.get(user=self.owner)
        )
        candidate.qualifying_position_assignment = assignments[0]
        candidate.routing_basis = [
            {
                "resolver": "position",
                "position_id": str(assignment.position_id),
                "position_assignment_id": str(assignment.pk),
            }
            for assignment in assignments
        ] + [{"resolver": "delegation"}, {"resolver": "escalation"}]
        candidate.save()
        due_at = timezone.now() - timedelta(hours=1)
        WorkItem.objects.filter(pk=item.pk).update(priority=42, due_at=due_at)
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="WB-SITE",
            name="کارگاه تست",
        )
        context = item.instance.subject_context | {"site_id": str(site.pk)}
        type(item.instance).objects.filter(pk=item.instance_id).update(
            subject_context=context
        )

        response = self.client.get(reverse("workflows:workbench"))

        self.assertEqual(response.context["counts"].all_items, 1)
        self.assertEqual(
            {entry["count"] for entry in response.context["counts"].positions}, {1}
        )
        self.assertContains(response, purchase_request.title, count=1)
        self.assertContains(response, "موضوع کار")
        self.assertContains(response, "دلیل دریافت")
        self.assertNotContains(response, "وضعیت و دلیل دریافت")
        self.assertNotContains(
            response, '<th class="border-b border-slate-200 px-4 py-3">سمت</th>'
        )
        self.assertContains(response, "erp-btn--compact")
        self.assertNotContains(response, "min-w-[920px]")
        self.assertContains(response, "عادی")
        self.assertEqual(
            response.context["work_items"][0].workbench_states,
            (("candidate", "جهت اقدام"),),
        )
        for label in ("جهت اقدام", "واگذاری موقت", "نیازمند پیگیری بالاتر"):
            self.assertContains(response, label)
        self.assertNotContains(response, "واگذارشده")

        filters = (
            {"workflow": "procurement.purchase_request_approval"},
            {"project": str(self.project.pk)},
            {"site": str(site.pk)},
            {"position": str(positions[1].pk)},
            {"priority": "normal"},
            {"due": "overdue"},
            {"assignment": "delegated"},
            {"assignment": "escalated"},
        )
        for params in filters:
            filtered = self.client.get(reverse("workflows:workbench"), params)
            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(len(filtered.context["work_items"]), 1, params)

        excluded = self.client.get(
            reverse("workflows:workbench"), {"priority": "urgent"}
        )
        self.assertEqual(len(excluded.context["work_items"]), 0)

    def test_work_reserved_by_another_member_is_excluded(self) -> None:
        purchase_request = self._submitted_request("WB-RESERVED")
        item = self._item(purchase_request)
        member_membership = self.organization.memberships.get(user=self.member)
        member_role = member_membership.role_definition
        member_role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    BusinessPermissionCode.PURCHASE_REQUESTS_VIEW,
                    BusinessPermissionCode.WORK_ITEMS_VIEW,
                    BusinessPermissionCode.WORK_ITEMS_CLAIM,
                )
            )
        )
        item.candidates.create(
            organization=self.organization,
            membership=member_membership,
            routing_basis=[{"resolver": "explicit_membership"}],
        )
        item.current_assignee = self.organization.memberships.get(user=self.owner)
        item.save(update_fields=["current_assignee", "updated_at"])

        self.client.force_login(self.member)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.get(reverse("workflows:workbench"))

        self.assertNotContains(response, purchase_request.title)
        self.assertNotContains(response, "قبول کار")
        for assignment in ("candidate", "assigned", "claimed"):
            filtered = self.client.get(
                reverse("workflows:workbench"), {"assignment": assignment}
            )
            self.assertEqual(len(filtered.context["work_items"]), 0)

        item.status = WorkItemStatus.CLAIMED
        item.save(update_fields=["status", "updated_at"])
        response = self.client.get(reverse("workflows:workbench"))
        self.assertNotContains(response, purchase_request.title)

    def test_pagination_responsive_context_and_query_bound(self) -> None:
        for index in range(26):
            self._submitted_request(f"WB-PAGE-{index:02d}")

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("workflows:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["work_items"]), 25)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertTrue(response.context["is_rtl"])
        self.assertTrue(response.context["responsive_table"])
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'class="erp-table-wrap"')
        self.assertLessEqual(len(queries), 25)

    def test_claim_release_action_stale_and_htmx_csrf(self) -> None:
        purchase_request = self._submitted_request("WB-ACTION")
        item = self._item(purchase_request)
        claim_url = reverse("workflows:work_item_claim", args=[item.pk])
        release_url = reverse("workflows:work_item_release", args=[item.pk])
        action_url = reverse("workflows:work_item_action", args=[item.pk])

        response = self.client.post(
            claim_url,
            {"idempotency_key": "claim-1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.CLAIMED)
        self.assertEqual(response.headers["HX-Trigger"], "workbenchActionSucceeded")
        self.assertContains(response, "قبول کار")
        self.assertContains(response, "واگذاری کار")

        response = self.client.post(
            release_url,
            {"idempotency_key": "release-1", "reason": "بازگشت به صف"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.OPEN)

        self.client.post(claim_url, {"idempotency_key": "claim-2"})
        response = self.client.post(
            action_url,
            {"idempotency_key": "action-1", "outcome": "approved"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Redirect"], reverse("workflows:workbench")
        )
        purchase_request.refresh_from_db()
        self.assertEqual(purchase_request.status, PurchaseRequestStatus.APPROVED)

        stale = self.client.post(
            action_url,
            {"idempotency_key": "action-stale", "outcome": "approved"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.headers["HX-Retarget"], "#workbench-feedback")

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        set_active_organization(csrf_client.session, self.organization)
        csrf_client.session.save()
        page = csrf_client.get(reverse("workflows:workbench"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="csrfmiddlewaretoken"')
        fresh_request = self._submitted_request("WB-CSRF")
        fresh_item = self._item(fresh_request)
        protected = csrf_client.post(
            reverse("workflows:work_item_claim", args=[fresh_item.pk]),
            {"idempotency_key": "csrf-missing"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(protected.status_code, 403)
        allowed = csrf_client.post(
            reverse("workflows:work_item_claim", args=[fresh_item.pk]),
            {"idempotency_key": "csrf-present"},
            HTTP_HX_REQUEST="true",
            HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
        )
        self.assertEqual(allowed.status_code, 200)

    def test_unprivileged_viewer_sees_no_mutation_controls(self) -> None:
        purchase_request = self._submitted_request("WB-VIEWER")
        item = self._item(purchase_request)
        viewer_membership = self.organization.memberships.get(user=self.viewer)
        item.candidates.create(
            organization=self.organization,
            membership=viewer_membership,
            routing_basis=[{"resolver": "explicit_membership"}],
        )
        self.client.force_login(self.viewer)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.get(reverse("workflows:workbench"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, purchase_request.title)
        self.assertNotContains(response, "قبول کار")
        forbidden = self.client.post(
            reverse("workflows:work_item_claim", args=[item.pk]),
            {"idempotency_key": "viewer-claim"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(forbidden.status_code, 409)
