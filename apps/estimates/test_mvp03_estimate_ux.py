"""Project-local Estimate navigation, safe appends and nonempty approval."""

from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.forms import EstimateForm, EstimateItemForm
from apps.estimates.models import Estimate, EstimateRevision, EstimateStatus
from apps.estimates.services import (
    EMPTY_ESTIMATE_APPROVAL_MESSAGE,
    add_estimate_item,
    approve_estimate,
    create_estimate,
    create_estimate_revision,
)
from apps.estimates.workflow import request_estimate_approval
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectSite
from apps.workflows.models import WorkflowInstanceStatus, WorkItemStatus


def seed_estimate_workflow():
    import_module(
        "apps.workflows.migrations.0015_estimate_contract_amendment_compatibility_catalog"
    ).seed_w54_catalog(apps, None)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateUXTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        seed_estimate_workflow()
        self.login(self.owner)
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EUX",
            name="متر",
            symbol="m",
            category="length",
        )
        self.estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="EUX-1",
            title="برآورد پروژه",
        )
        self.detail = reverse("estimates:detail", args=[self.estimate.pk])
        self.context = f"?project_id={self.project.pk}"
        self.list_url = reverse("estimates:list") + self.context
        self.create_url = reverse("estimates:create") + self.context

    def item_data(self, **overrides):
        return {
            "description": "ردیف اجرایی",
            "quantity": "2",
            "unit_price": "10",
            "unit_of_measure": self.unit.pk,
            **overrides,
        }

    def add_item(self, **overrides):
        return add_estimate_item(
            estimate=self.estimate,
            actor=self.owner,
            description="ردیف اجرایی",
            quantity=Decimal(1),
            unit_price=Decimal(10),
            **overrides,
        )

    def test_project_list_detail_back_create_and_posts_preserve_context(self):
        sibling = Project.objects.create(
            organization=self.organization, code="EUX-OTHER", name="پروژه فعال دیگر"
        )
        session = self.client.session
        session["active_project_id"] = str(sibling.pk)
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=sibling,
            code="EUX-ACTIVE-S",
            name="کارگاه فعال دیگر",
        )
        session["active_site_id"] = str(site.pk)
        session.save()
        before = dict(self.client.session)
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertContains(response, self.detail + self.context)
        self.assertContains(response, self.create_url)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.detail + self.context, count=3)
        self.assertEqual(response.context["estimate_create_url"], self.create_url)
        response = self.client.get(self.detail + self.context)
        self.assertEqual(response.context["page_breadcrumbs"][-2]["url"], self.list_url)
        response = self.client.post(
            self.detail + self.context, self.item_data(quantity="0")
        )
        self.assertRedirects(response, self.detail + self.context)
        response = self.client.post(
            self.detail + self.context, self.item_data(description="")
        )
        self.assertTrue(response.context["item_form"].errors)
        self.assertEqual(response.context["page_breadcrumbs"][-2]["url"], self.list_url)
        response = self.client.post(self.detail + self.context, self.item_data())
        self.assertRedirects(response, self.detail + self.context)
        data = {"project": self.project.pk, "estimate_number": "EUX-NEW", "title": ""}
        response = self.client.post(self.create_url, data)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(response.context["page_breadcrumbs"][-2]["url"], self.list_url)
        data["title"] = "برآورد جدید پروژه"
        response = self.client.post(self.create_url, data)
        created = Estimate.objects.get(estimate_number="EUX-NEW")
        self.assertRedirects(
            response, reverse("estimates:detail", args=[created.pk]) + self.context
        )
        response = self.client.post(
            reverse("estimates:approve", args=[self.estimate.pk]) + self.context
        )
        self.assertRedirects(response, self.detail + self.context)
        self.assertEqual(dict(self.client.session), before)

    def test_global_entry_remains_global_and_legacy_project_create_retains_context(
        self,
    ):
        response = self.client.get(self.detail)
        self.assertEqual(
            response.context["page_breadcrumbs"][-2]["url"], reverse("estimates:list")
        )
        response = self.client.get(reverse("estimates:list"))
        self.assertEqual(
            response.context["estimate_create_url"], reverse("estimates:create")
        )
        self.assertNotContains(response, self.detail + self.context)
        response = self.client.get(
            reverse("estimates:create") + f"?project={self.project.pk}"
        )
        self.assertEqual(response.context["page_breadcrumbs"][-2]["url"], self.list_url)

    def test_invalid_ambiguous_foreign_and_mismatched_contexts_fail_closed(self):
        tenant = Organization.objects.create(name="Other", slug="eux-other")
        foreign = Project.objects.create(
            organization=tenant, code="EUX-F", name="پروژه محرمانه"
        )
        sibling = Project.objects.create(
            organization=self.organization, code="EUX-S", name="پروژه دیگر"
        )
        for path in (self.detail, reverse("estimates:create")):
            for query in (
                "?project_id=bad",
                "?project_id=",
                f"?project_id={foreign.pk}",
                self.context + f"&project_id={self.project.pk}",
            ):
                with self.subTest(path=path, query=query):
                    self.assertEqual(self.client.get(path + query).status_code, 404)
        self.assertEqual(
            self.client.get(self.detail + f"?project_id={sibling.pk}").status_code, 404
        )
        self.assertEqual(
            self.client.get(self.create_url + f"&project={sibling.pk}").status_code, 404
        )
        response = self.client.post(
            self.create_url,
            {"project": sibling.pk, "estimate_number": "EUX-FORGED", "title": "Forged"},
        )
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Estimate.objects.filter(estimate_number="EUX-FORGED").exists())

    def test_item_ui_omits_order_and_automatic_append_uses_existing_current_orders(
        self,
    ):
        self.assertNotIn(
            "sort_order", EstimateItemForm(organization=self.organization).fields
        )
        self.add_item(sort_order=12)
        for description in ("ردیف دوم", "ردیف سوم"):
            response = self.client.post(
                self.detail, self.item_data(description=description, sort_order="999")
            )
            self.assertRedirects(response, self.detail)
        self.assertEqual(
            list(
                self.estimate.current_revision.items.values_list(
                    "sort_order", flat=True
                )
            ),
            [12, 13, 14],
        )
        response = self.client.get(self.detail)
        self.assertNotContains(response, 'name="sort_order"')
        self.assertNotContains(response, "ترتیب نمایش")
        self.assertContains(response, 'data-business-choice="unit_of_measure"')

    def test_empty_estimate_rejected_by_service_and_forged_post_without_approval(self):
        response = self.client.get(self.detail)
        self.assertContains(response, EMPTY_ESTIMATE_APPROVAL_MESSAGE)
        self.assertNotContains(
            response,
            'action="' + reverse("estimates:approve", args=[self.estimate.pk]) + '"',
        )
        with self.assertRaisesMessage(ValueError, EMPTY_ESTIMATE_APPROVAL_MESSAGE):
            approve_estimate(estimate=self.estimate, actor=self.owner)
        response = self.client.post(
            reverse("estimates:approve", args=[self.estimate.pk])
        )
        self.assertContains(response, EMPTY_ESTIMATE_APPROVAL_MESSAGE, status_code=403)
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.status, EstimateStatus.DRAFT)
        self.assertEqual(self.estimate.current_revision.status, "draft")
        self.assertIsNone(self.estimate.approved_at)

    def test_historical_items_do_not_qualify_an_empty_current_revision(self):
        self.add_item(sort_order=50)
        approve_estimate(estimate=self.estimate, actor=self.owner)
        historical = self.estimate.current_revision
        empty = EstimateRevision.objects.create(
            organization=self.organization, estimate=self.estimate, revision_number=2
        )
        Estimate.objects.filter(pk=self.estimate.pk).update(
            current_revision=empty, status="draft"
        )
        self.estimate.refresh_from_db()
        with self.assertRaisesMessage(ValueError, EMPTY_ESTIMATE_APPROVAL_MESSAGE):
            approve_estimate(estimate=self.estimate, actor=self.owner)
        self.assertEqual(self.add_item().sort_order, 1)
        historical.refresh_from_db()
        self.assertEqual(historical.status, "approved")

    def test_legacy_empty_revision_fallback_is_rolled_back(self):
        Estimate.objects.filter(pk=self.estimate.pk).update(current_revision=None)
        self.estimate.revisions.all().delete()
        self.estimate.refresh_from_db()
        with self.assertRaisesMessage(ValueError, EMPTY_ESTIMATE_APPROVAL_MESSAGE):
            approve_estimate(estimate=self.estimate, actor=self.owner)
        self.estimate.refresh_from_db()
        self.assertIsNone(self.estimate.current_revision_id)
        self.assertFalse(self.estimate.revisions.exists())

    def test_workflow_command_rejects_empty_atomically_and_valid_revision_completes(
        self,
    ):
        instance = request_estimate_approval(estimate=self.estimate, actor=self.owner)
        work_item = instance.work_items.get()
        with self.assertRaisesMessage(ValueError, EMPTY_ESTIMATE_APPROVAL_MESSAGE):
            approve_estimate(estimate=self.estimate, actor=self.owner)
        work_item.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(work_item.status, WorkItemStatus.OPEN)
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        self.add_item()
        approve_estimate(estimate=self.estimate, actor=self.owner)
        instance.refresh_from_db()
        self.estimate.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(self.estimate.status, "approved")
        revision = create_estimate_revision(estimate=self.estimate, actor=self.owner)
        self.assertEqual(self.add_item().sort_order, 2)
        self.assertEqual(revision.items.count(), 2)

    def test_permission_checks_still_precede_empty_approval(self):
        with self.assertRaises(PermissionDenied):
            approve_estimate(estimate=self.estimate, actor=self.member)
        self.login(self.member)
        self.assertEqual(
            self.client.post(
                reverse("estimates:approve", args=[self.estimate.pk])
            ).status_code,
            403,
        )

    def test_create_form_identifies_optional_fields_and_keeps_notes_compact(self):
        form = EstimateForm(organization=self.organization)
        for name in ("contract", "phase"):
            self.assertFalse(form.fields[name].required)
            self.assertIn("اختیاری", form.fields[name].label)
        self.assertEqual(form.fields["notes"].widget.attrs["rows"], 3)

    def test_global_detail_does_not_add_project_view_permission_requirement(self):
        from apps.accounts.models import User
        from apps.organizations.models import (
            BusinessPermission,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )

        actor = User.objects.create_user(username="eux-estimate-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="eux-reader", name="خواننده برآورد"
        )
        role.permissions.add(BusinessPermission.objects.get(code="estimates.view"))
        member = self.organization.memberships.create(
            user=actor, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=role,
            reason="Explicit estimate-only reader fixture",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=self.project,
            reason="Explicit reader project scope",
        )
        self.login(actor)
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["project_detail_url"], "")
        self.assertEqual(
            response.context["page_breadcrumbs"][-2]["url"], reverse("estimates:list")
        )
        self.assertEqual(
            self.client.post(self.detail, self.item_data()).status_code, 403
        )
        other = Project.objects.create(
            organization=self.organization, code="EUX-SCOPE", name="پروژه دیگر"
        )
        grant.project = other
        grant.save()
        self.assertEqual(self.client.get(self.detail).status_code, 404)
