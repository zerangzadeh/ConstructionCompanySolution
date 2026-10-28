"""MVP-01 exposure, HTTP, shared entry and authorization regression evidence."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.projects.models import Project
from apps.reporting.read_models import MetricCard, ReportingLayer, ReportingReadModel
from apps.workforce.models import Employee
from core.financial_navigation import authorized_financial_authorities
from core.product_surface import (
    CAPABILITIES,
    NAVIGATION_GROUPS,
    capability_exposed,
    metric_exposed,
    navigation_groups,
    route_exposed,
    url_exposed,
    workflow_subject_exposed,
)


def grant_test_reporting_permission(user, organization):
    membership = OrganizationMembership.objects.get(
        user=user, organization=organization
    )
    role = OrganizationRole.objects.create(
        organization=organization, code="mvp01_reporting", name="Test reporting reader"
    )
    role.permissions.add(
        BusinessPermission.objects.get(code="reporting.metric_result.view")
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=membership,
        role=role,
        reason="Explicit synthetic MVP-01 reporting verification",
    )


def create_test_own_leave(user, organization, employee=None):
    from datetime import timedelta

    from django.utils import timezone

    from apps.timekeeping.models import LeaveMissionRequest, RequestKind
    from apps.workforce.models import Person, WorkRelationship

    membership = OrganizationMembership.objects.get(
        user=user, organization=organization
    )
    role = OrganizationRole.objects.create(
        organization=organization, code="mvp01_own_time", name="Test own time reader"
    )
    role.permissions.add(
        BusinessPermission.objects.get(
            code=BusinessPermissionCode.LEAVE_MISSION_REQUEST
        )
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=membership,
        role=role,
        reason="Explicit synthetic own-Timekeeping preservation verification",
    )
    employee = employee or Employee.objects.create(
        organization=organization,
        employee_number="MVP01-OWN",
        first_name="Test",
        last_name="Worker",
    )
    person = Person.objects.create(
        organization=organization, user=user, first_name="Test", last_name="Worker"
    )
    WorkRelationship.objects.create(
        organization=organization,
        person=person,
        legacy_employee=employee,
        employee_number=employee.employee_number,
        effective_start=timezone.localdate() - timedelta(days=1),
    )
    start = timezone.now() + timedelta(days=1)
    return LeaveMissionRequest.objects.create(
        organization=organization,
        employee=employee,
        kind=RequestKind.LEAVE,
        category_code="ANNUAL",
        starts_at=start,
        ends_at=start + timedelta(hours=8),
        requested_by=user,
        reason="Synthetic own Timekeeping request",
    )


class SurfacePolicyTests(SimpleTestCase):
    def test_capabilities_are_unique_and_unknown_fails_closed(self):
        self.assertEqual(len(CAPABILITIES), len({c.key for c in CAPABILITIES}))
        self.assertFalse(capability_exposed("unknown"))
        self.assertFalse(route_exposed("future:workspace"))
        self.assertFalse(url_exposed("https://external.invalid/projects/"))
        self.assertFalse(url_exposed("/unregistered/"))

    def test_mixed_capabilities_share_namespaces_without_sharing_exposure(self):
        for route in (
            "workforce:employee_list",
            "workforce:assignment_create",
            "timekeeping:workbench",
            "expenses:list",
            "organizations:members",
            "reporting:dashboard",
        ):
            self.assertTrue(route_exposed(route), route)
        for route in (
            "workforce:ess_dashboard",
            "workforce:foundation",
            "workforce:employment_manage",
            "treasury:workbench",
            "organizations:reference_personas",
            "reporting:reconciliation_workbench",
            "reporting:export",
            "expenses:platform_group_list",
        ):
            self.assertFalse(route_exposed(route), route)

    def test_internal_profile_is_explicit_and_grants_no_unknown_capability(self):
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            self.assertTrue(route_exposed("treasury:workbench"))
            self.assertTrue(route_exposed("workforce:ess_dashboard"))
            self.assertFalse(route_exposed("future:workspace"))
        self.assertFalse(route_exposed("treasury:workbench"))
        with (
            override_settings(PRODUCT_SURFACE_PROFILE="invalid"),
            self.assertRaises(ImproperlyConfigured),
        ):
            route_exposed("projects:list")

    def test_navigation_permissions_empty_groups_and_operational_reports(self):
        groups = navigation_groups({"expenses.view", "rfqs.view"})
        self.assertEqual(
            [g.key for g in groups], ["operations", "materials", "foundation"]
        )
        routes = {link.route for group in groups for link in group.links}
        self.assertIn("expenses:list", routes)
        self.assertNotIn("projects:list", routes)
        self.assertEqual(len(NAVIGATION_GROUPS), 5)
        self.assertTrue(metric_exposed("procurement_cycle_time"))
        self.assertFalse(metric_exposed("cleared_cash_position"))
        self.assertFalse(workflow_subject_exposed("workforce.offboarding"))
        self.assertTrue(workflow_subject_exposed("billing.progress_claim"))

    def test_dynamic_shared_links_use_central_resolver_and_keep_plain_labels(self):
        template = Template('{% include "components/record_detail_link.html" %}')
        self.assertIn(
            'href="/projects/"', template.render(Context({"detail_url": "/projects/"}))
        )
        self.assertNotIn(
            "href=",
            template.render(
                Context({"detail_url": "/treasury/?profile=FULL_ERP#cash"})
            ),
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProductSurfaceHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="mvp01-owner")
        cls.organization = create_organization_with_owner(
            owner=cls.owner, name="MVP Test Company", slug="mvp01"
        )
        grant_test_reporting_permission(cls.owner, cls.organization)
        cls.other = User.objects.create_user(username="mvp01-other")
        cls.other_organization = create_organization_with_owner(
            owner=cls.other, name="Other Private Company", slug="mvp01-other"
        )
        cls.project = Project.objects.create(
            organization=cls.organization, code="MVP", name="Visible Project"
        )
        cls.foreign = Project.objects.create(
            organization=cls.other_organization, code="PRIVATE", name="Private Project"
        )
        cls.employee = Employee.objects.create(
            organization=cls.organization,
            employee_number="MVP01",
            first_name="Test",
            last_name="Worker",
        )
        cls.foreign_employee = Employee.objects.create(
            organization=cls.other_organization,
            employee_number="MVP02",
            first_name="Private",
            last_name="Worker",
        )
        cls.restricted = User.objects.create_user(username="mvp01-restricted")
        role = OrganizationRole.objects.create(
            code="mvp01_expenses", name="Expense reader"
        )
        role.permissions.add(BusinessPermission.objects.get(code="expenses.view"))
        membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.restricted,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=cls.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def test_home_desktop_mobile_and_admin_navigation_share_five_groups(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [group.key for group in response.context["product_navigation_groups"]],
            [g.key for g in NAVIGATION_GROUPS],
        )
        for group in NAVIGATION_GROUPS:
            self.assertContains(response, f'data-surface-group="{group.key}"', count=2)
        for route in (
            "treasury:workbench",
            "accounting:dashboard",
            "workforce:ess_dashboard",
            "payroll:workbench",
            "organizations:reference_personas",
        ):
            self.assertNotContains(response, f'href="{reverse(route)}"')
        self.assertContains(response, reverse("organizations:members"))

    def test_hidden_http_get_post_and_htmx_fail_without_calling_domain_view(self):
        routes = (
            "treasury:workbench",
            "accounting:dashboard",
            "subledgers:workbench",
            "financials:dashboard",
            "fixed_assets:workbench",
            "payroll:workbench",
            "workforce:foundation",
            "workforce:ess_dashboard",
            "workforce:employment_manage",
            "reporting:reconciliation_workbench",
            "reporting:project_closeout_workbench",
            "organizations:reference_personas",
            "organizations:platform_role_catalog",
            "expenses:platform_group_list",
        )
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "Traceback", status_code=403)
        with patch("apps.treasury.views.render") as domain:
            for method in (self.client.get, self.client.post):
                response = method(
                    reverse("treasury:workbench") + "?profile=FULL_ERP",
                    {"profile": "FULL_ERP"},
                    HTTP_HX_REQUEST="true",
                )
                self.assertEqual(response.status_code, 403)
            domain.assert_not_called()

    def test_visible_operations_and_workforce_detail_keep_existing_guards(self):
        for route in (
            "projects:list",
            "expenses:list",
            "workforce:employee_list",
            "timekeeping:workbench",
            "reporting:dashboard",
            "organizations:settings",
        ):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200, route)
        response = self.client.get(
            reverse("workforce:employee_detail", args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        for route in (
            "workforce:foundation",
            "workforce:department_list",
            "workforce:position_list",
        ):
            self.assertNotContains(response, f'href="{reverse(route)}"')

    def test_permission_and_exposure_are_intersections(self):
        self.client.force_login(self.restricted)
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="/expenses/"')
        self.assertNotContains(response, 'href="/projects/"')
        self.assertNotContains(response, 'href="/organizations/members/"')
        self.assertEqual(self.client.get(reverse("projects:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("expenses:list")).status_code, 200)
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            self.assertEqual(
                self.client.get(reverse("treasury:workbench")).status_code, 403
            )

    def test_tenant_switch_object_reads_and_writes_fail_closed(self):
        response = self.client.get(reverse("projects:detail", args=[self.foreign.pk]))
        self.assertNotEqual(response.status_code, 200)
        response = self.client.get(
            reverse("workforce:employee_detail", args=[self.foreign_employee.pk])
        )
        self.assertNotEqual(response.status_code, 200)
        response = self.client.post(
            reverse(
                "workforce:employee_status_change", args=[self.foreign_employee.pk]
            ),
            {"target_status": "inactive"},
        )
        self.assertNotEqual(response.status_code, 200)
        self.foreign_employee.refresh_from_db()
        self.assertEqual(self.foreign_employee.status, "active")
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.other_organization.pk)
        session.save()
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.other_organization.name, status_code=403)

    def test_revoked_membership_and_superuser_do_not_bypass_product_boundary(self):
        self.owner.is_superuser = True
        self.owner.save(update_fields=["is_superuser"])
        self.assertEqual(
            self.client.get(reverse("treasury:workbench")).status_code, 403
        )
        OrganizationMembership.objects.filter(user=self.owner).update(
            status=MembershipStatus.REVOKED
        )
        self.assertNotEqual(self.client.get(reverse("expenses:list")).status_code, 200)

    def test_financial_shortcuts_preserve_expenses_and_remove_cash_workspace(self):
        routes = {
            link.route
            for link in authorized_financial_authorities(
                user=self.owner, organization=self.organization
            )
        }
        self.assertIn("expenses:list", routes)
        self.assertNotIn("treasury:workbench", routes)

    def test_reporting_filters_retained_cash_projection_after_authorization(self):
        from django.utils import timezone

        def card(code):
            return MetricCard(SimpleNamespace(metric_code=code), True, True, True)

        model = ReportingReadModel(
            timezone.now(),
            timezone.now(),
            (
                ReportingLayer(
                    "operational",
                    "عملیاتی",
                    "",
                    (card("cleared_cash_position"), card("procurement_cycle_time")),
                ),
            ),
        )
        # Inspect the actual view projection without requiring a fabricated source run.
        with (
            patch("apps.reporting.views.reporting_layers", return_value=model),
            patch("apps.reporting.views.render") as render,
        ):
            render.return_value = HttpResponse()
            self.client.get(reverse("reporting:dashboard"))
        projected = render.call_args.args[2]["read_model"]
        self.assertEqual(
            [c.result.metric_code for c in projected.layers[0].cards],
            ["procurement_cycle_time"],
        )
        self.assertFalse(projected.layers[0].cards[0].can_drillthrough)

    def test_hidden_workflow_proxy_cannot_invoke_runtime(self):
        item = SimpleNamespace(
            instance=SimpleNamespace(subject_type="workforce.personal_data_change")
        )
        with (
            patch("apps.workflows.views.WorkItem.objects.filter") as items,
            patch("apps.workflows.views.complete_work_item") as complete,
        ):
            items.return_value.select_related.return_value.first.return_value = item
            self.client.post(
                reverse("workflows:work_item_action", args=[uuid4()]),
                {"outcome": "approved", "idempotency_key": "mvp01-hidden"},
            )
        complete.assert_not_called()

    def test_internal_profile_reaches_original_authorized_hidden_view(self):
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            self.assertEqual(
                self.client.get(reverse("treasury:workbench")).status_code, 200
            )
        self.assertEqual(
            self.client.get(reverse("treasury:workbench")).status_code, 403
        )

    def test_own_timekeeping_status_preserves_identity_and_source_ownership(self):
        from apps.workforce.models import Person

        leave = create_test_own_leave(self.owner, self.organization, self.employee)
        url = reverse("workforce:ess_request_status", args=["leave", leave.pk])
        self.assertTrue(url_exposed(url))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("workflows:my_requests"))
        self.assertNotContains(response, 'href="/workforce/ess/"')
        self.assertContains(self.client.get(reverse("workflows:my_requests")), url)
        for kind, identifier in (
            ("leave", uuid4()),
            ("personal_data", leave.pk),
            ("payroll_inquiry", leave.pk),
        ):
            self.assertEqual(
                self.client.get(
                    reverse("workforce:ess_request_status", args=[kind, identifier])
                ).status_code,
                403,
            )
        Person.objects.filter(user=self.owner, organization=self.organization).update(
            user=None
        )
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_home_keeps_own_requests_without_backoffice_permissions(self):
        create_test_own_leave(self.restricted, self.organization)
        self.client.force_login(self.restricted)
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-home-state="normal"')
        groups = response.context["home_groups"]
        self.assertIn(
            "workflows:my_requests",
            {link.route for group in groups for link in group.links},
        )
        self.assertNotContains(response, 'href="/projects/"')
        self.assertEqual(
            self.client.get(reverse("workflows:my_requests")).status_code, 200
        )
