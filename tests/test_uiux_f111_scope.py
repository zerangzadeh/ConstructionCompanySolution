"""F-111 disclosure boundaries, using explicit grants and a nonprivileged actor.

All records in this module belong to Django's disposable test database. No
persistent UIUX persona, catalogue, or Development business fixture is modified.
"""

from datetime import timedelta
from typing import ClassVar

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.daily_reports.forms import DailyReportForm
from apps.daily_reports.models import DailyReport
from apps.daily_reports.services import create_daily_report
from apps.equipment.forms import EquipmentAssignmentForm
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.services import assign_equipment
from apps.estimates.forms import EstimateForm
from apps.expenses.forms import ExpenseForm
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationStatus,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty, PartyKind, PartyRole, PartyRoleType
from apps.procurement.forms import PurchaseOrderForm
from apps.procurement.models import (
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestStatus,
)
from apps.procurement.services import create_purchase_order
from apps.projects.models import Project, ProjectPhase, ProjectPhaseStatus, ProjectSite
from apps.workforce.forms import EmployeeAssignmentForm
from apps.workforce.models import Employee, EmployeeProjectAssignment
from apps.workforce.services import assign_employee_to_project


class F111SelectorScopeTests(TestCase):
    surfaces: ClassVar[dict] = {
        "daily": ("daily_reports:create", DailyReportForm, DailyReport),
        "equipment": (
            "equipment:assignment_create",
            EquipmentAssignmentForm,
            EquipmentAssignment,
        ),
        "order": ("procurement:order_create", PurchaseOrderForm, PurchaseOrder),
        "workforce": (
            "workforce:assignment_create",
            EmployeeAssignmentForm,
            EmployeeProjectAssignment,
        ),
    }

    @classmethod
    def setUpTestData(cls) -> None:
        cls.organization = Organization.objects.create(
            name="F111 Tenant A", slug="f111-a"
        )
        cls.other_organization = Organization.objects.create(
            name="F111 Tenant B", slug="f111-b"
        )
        cls.user = User.objects.create_user(username="f111-scoped-member")
        cls.membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.user,
            role=MembershipRole.PROJECT_MANAGER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=cls.organization,
            membership=cls.membership,
            role=OrganizationRole.objects.get(code=MembershipRole.PROJECT_MANAGER),
            reason="F111 isolated test actor",
        )
        other_user = User.objects.create_user(username="f111-other-member")
        cls.other_membership = OrganizationMembership.objects.create(
            organization=cls.other_organization,
            user=other_user,
            role=MembershipRole.PROJECT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        cls.projects, cls.sites, cls.phases, cls.requests, cls.contracts = (
            {},
            {},
            {},
            {},
            {},
        )
        for key in ("A", "B", "C", "D", "X"):
            organization = cls.other_organization if key == "X" else cls.organization
            project = Project.objects.create(
                organization=organization,
                code=f"F111-P-{key}",
                name=f"F111 Project {key} label",
            )
            cls.projects[key] = project
            cls.sites[key] = ProjectSite.objects.create(
                organization=organization,
                project=project,
                code=f"F111-S-{key}",
                name=f"F111 Site {key} label",
            )
            cls.phases[key] = ProjectPhase.objects.create(
                organization=organization,
                site=cls.sites[key],
                code=f"F111-PH-{key}",
                name=f"F111 Phase {key} label",
                status=ProjectPhaseStatus.ACTIVE,
            )
            cls.requests[key] = PurchaseRequest.objects.create(
                organization=organization,
                project=project,
                request_number=f"F111-REQ-{key}",
                title=f"F111 Request {key} title",
                status=PurchaseRequestStatus.APPROVED,
            )
            cls.contracts[key] = Contract.objects.create(
                organization=organization,
                project=project,
                contract_number=f"F111-CON-{key}",
                title=f"F111 Contract {key} title",
                counterparty_name="F111 counterparty",
            )
            if key in ("A", "B"):
                MembershipScopeGrant.objects.create(
                    organization=cls.organization,
                    membership=cls.membership,
                    scope_type=AuthorizationScopeType.PROJECT,
                    project=project,
                    reason="F111 test authorized project",
                )
        cls.sibling_site = ProjectSite.objects.create(
            organization=cls.organization,
            project=cls.projects["A"],
            code="F111-SIBLING",
            name="F111 ungranted sibling site",
        )
        cls.sibling_phase = ProjectPhase.objects.create(
            organization=cls.organization,
            site=cls.sibling_site,
            code="F111-PH-SIBLING",
            name="F111 ungranted sibling phase",
            status=ProjectPhaseStatus.ACTIVE,
        )
        cls.equipment = Equipment.objects.create(
            organization=cls.organization,
            code="F111-EQ",
            name="F111 Equipment",
            category="F111 category",
        )
        cls.employee = Employee.objects.create(
            organization=cls.organization,
            employee_number="F111-EMP",
            first_name="F111",
            last_name="Employee",
        )
        cls.supplier = BusinessParty.objects.create(
            organization=cls.organization,
            party_kind=PartyKind.COMPANY,
            display_name="F111 Supplier",
        )
        PartyRole.objects.create(
            organization=cls.organization,
            party=cls.supplier,
            role=PartyRoleType.SUPPLIER,
        )

    def setUp(self) -> None:
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def form(self, surface, data=None, **kwargs):
        return self.surfaces[surface][1](
            data=data,
            organization=self.organization,
            **({"membership": self.membership} | kwargs),
        )

    def test_dependent_choice_metadata_preserves_scope_and_prefixed_controls(self):
        for surface in ("daily", "equipment"):
            with self.subTest(surface=surface):
                form = self.form(surface, prefix="cascade")
                site_html = str(form["site"])
                self.assertIn('data-local-parent="id_cascade-project"', site_html)
                self.assertIn(f'data-parent-value="{self.projects["A"].pk}"', site_html)
                for key in ("C", "D", "X"):
                    self.assertNotIn(str(self.sites[key].pk), site_html)
                if surface == "daily":
                    phase_html = str(form["phase"])
                    self.assertIn('data-local-parent="id_cascade-site"', phase_html)
                    self.assertIn(
                        f'data-parent-value="{self.sites["A"].pk}"', phase_html
                    )

    def payload(self, surface, key="A"):
        project, site = self.projects[key], self.sites[key]
        common = {"project": str(project.pk)}
        today = timezone.localdate().isoformat()
        if surface == "daily":
            return common | {
                "site": str(site.pk),
                "phase": str(self.phases[key].pk),
                "reporting_date": today,
                "labor_count": "1",
                "work_performed": "F111 scoped daily work",
            }
        if surface == "equipment":
            return common | {
                "site": str(site.pk),
                "equipment": str(self.equipment.pk),
                "start_date": today,
            }
        if surface == "order":
            return common | {
                "purchase_request": str(self.requests[key].pk),
                "supplier": str(self.supplier.pk),
                "order_number": "F111-ORDER",
                "order_date": today,
            }
        return common | {
            "site": str(site.pk),
            "employee": str(self.employee.pk),
            "start_date": today,
        }

    def assert_safe_body(self, response, keys=("C", "D", "X"), supplied_project=None):
        body = response.content.decode()
        for key in keys:
            for record in (
                self.projects[key],
                self.sites[key],
                self.phases[key],
                self.requests[key],
                self.contracts[key],
            ):
                # Denial-page navigation may echo the caller's own request URL.
                # It must still disclose no fetched labels or child identifiers.
                if record != supplied_project:
                    self.assertNotIn(str(record.pk), body)
                for attribute in (
                    "name",
                    "code",
                    "title",
                    "request_number",
                    "contract_number",
                ):
                    if value := getattr(record, attribute, None):
                        self.assertNotIn(value, body)

    def assert_project_choices(self, form, keys=("A", "B")):
        self.assertSetEqual(
            set(form.fields["project"].queryset.values_list("pk", flat=True)),
            {self.projects[key].pk for key in keys},
        )

    def assert_protected_choices_empty(self, form):
        for name in ("project", "site", "phase", "purchase_request"):
            if name in form.fields:
                self.assertFalse(form.fields[name].queryset.exists(), name)

    def site_only_scope(self):
        self.membership.scope_grants.update(revoked_at=timezone.now())
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.SITE,
            project=self.projects["A"],
            site=self.sites["A"],
            reason="F111 site-only test",
        )

    def test_actor_has_only_explicit_project_manager_role_and_a_b_grants(self):
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(
            list(self.membership.role_assignments.values_list("role__code", flat=True)),
            [MembershipRole.PROJECT_MANAGER],
        )
        self.assertSetEqual(
            set(self.membership.scope_grants.values_list("project_id", flat=True)),
            {self.projects["A"].pk, self.projects["B"].pk},
        )

    def test_initial_get_scopes_every_surface_and_response_body(self):
        for surface, (route, _, _) in self.surfaces.items():
            with self.subTest(surface=surface):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assert_project_choices(response.context["form"])
                for key in ("A", "B"):
                    self.assertContains(response, str(self.projects[key].pk))
                    self.assertContains(response, self.projects[key].name)
                self.assert_safe_body(response)

    def test_initial_child_choices_are_scoped_and_workforce_waits_for_parent(self):
        for surface in ("daily", "equipment"):
            form = self.form(surface)
            self.assertSetEqual(
                set(form.fields["site"].queryset),
                {self.sites["A"], self.sites["B"], self.sibling_site},
            )
        self.assertSetEqual(
            set(self.form("daily").fields["phase"].queryset),
            {self.phases["A"], self.phases["B"], self.sibling_phase},
        )
        self.assertSetEqual(
            set(self.form("order").fields["purchase_request"].queryset),
            {self.requests["A"], self.requests["B"]},
        )
        self.assertFalse(self.form("workforce").fields["site"].queryset.exists())

    def test_bound_authorized_second_parent_is_usable_on_every_form(self):
        for surface in self.surfaces:
            with self.subTest(surface=surface):
                form = self.form(surface, self.payload(surface, "B"))
                self.assertTrue(form.is_valid(), form.errors.as_json())
                self.assert_project_choices(form)

    def test_unauthorized_posts_are_rejected_without_creating_business_objects(self):
        for surface, (route, _, model) in self.surfaces.items():
            for key in ("C", "D", "X"):
                with self.subTest(surface=surface, project=key):
                    before = model.objects.count()
                    response = self.client.post(
                        reverse(route), self.payload(surface, key)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("project", response.context["form"].errors)
                    self.assertEqual(model.objects.count(), before)
                    self.assert_safe_body(response)

    def test_invalid_post_redisplay_keeps_authorized_choices_only(self):
        for surface, (route, _, _) in self.surfaces.items():
            with self.subTest(surface=surface):
                response = self.client.post(
                    reverse(route), {"project": str(self.projects["B"].pk)}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assert_project_choices(response.context["form"])
                self.assert_safe_body(response)

    def test_mixed_authorized_parent_children_are_rejected(self):
        for surface, (route, _, model) in self.surfaces.items():
            with self.subTest(surface=surface):
                data = self.payload(surface)
                child = "purchase_request" if surface == "order" else "site"
                record = self.requests["B"] if surface == "order" else self.sites["B"]
                data[child] = str(record.pk)
                before = model.objects.count()
                response = self.client.post(reverse(route), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(child, response.context["form"].errors)
                self.assertEqual(model.objects.count(), before)
                self.assert_safe_body(response)

    def test_phase_from_another_authorized_site_is_rejected(self):
        data = self.payload("daily") | {"phase": str(self.phases["B"].pk)}
        response = self.client.post(reverse("daily_reports:create"), data)
        self.assertIn("phase", response.context["form"].errors)
        self.assertFalse(DailyReport.objects.exists())
        self.assert_safe_body(response)

    def test_missing_invalid_or_wrong_tenant_membership_fails_closed(self):
        for surface in self.surfaces:
            for membership in (None, object(), self.other_membership):
                for data in (None, self.payload(surface)):
                    with self.subTest(
                        surface=surface, membership=membership, bound=bool(data)
                    ):
                        form = self.form(surface, data, membership=membership)
                        self.assert_protected_choices_empty(form)

    def test_inactive_membership_fails_closed_in_forms_and_http(self):
        self.membership.status = MembershipStatus.SUSPENDED
        self.membership.save(update_fields=["status"])
        for surface, (route, _, _) in self.surfaces.items():
            self.assert_protected_choices_empty(
                self.form(surface, self.payload(surface))
            )
            response = self.client.get(reverse(route))
            self.assertIn(response.status_code, (302, 403))
            self.assert_safe_body(response)
        response = self.client.get(
            reverse("workforce:assignment_sites"), {"project": self.projects["A"].pk}
        )
        self.assertIn(response.status_code, (302, 403))
        self.assert_safe_body(response, keys=("A", "B", "C", "D", "X"))

    def test_inactive_user_fails_closed_in_protected_form_choices(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        for surface in self.surfaces:
            self.assert_protected_choices_empty(
                self.form(surface, self.payload(surface))
            )

    def test_suspended_tenant_fails_closed_in_protected_form_choices(self):
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status"])
        for surface in self.surfaces:
            self.assert_protected_choices_empty(
                self.form(surface, self.payload(surface))
            )

    def test_revoked_grant_disappears_from_forms_and_http(self):
        self.membership.scope_grants.filter(project=self.projects["A"]).update(
            revoked_at=timezone.now()
        )
        self.assert_removed_a_grant()

    def test_expired_grant_disappears_from_forms_and_http(self):
        now = timezone.now()
        self.membership.scope_grants.filter(project=self.projects["A"]).update(
            starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1)
        )
        self.assert_removed_a_grant()

    def assert_removed_a_grant(self):
        for surface, (route, _, _) in self.surfaces.items():
            self.assert_project_choices(self.form(surface), keys=("B",))
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assert_safe_body(response, keys=("A", "C", "D", "X"))
        response = self.client.get(
            reverse("workforce:assignment_sites"), {"project": self.projects["A"].pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assert_safe_body(response, keys=("A", "C", "D", "X"))

    def test_future_grant_does_not_expose_choices(self):
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.projects["C"],
            starts_at=timezone.now() + timedelta(days=1),
            reason="F111 future grant",
        )
        for surface in self.surfaces:
            self.assert_project_choices(self.form(surface))

    def test_no_grants_fails_closed(self):
        self.membership.scope_grants.update(revoked_at=timezone.now())
        for surface, (route, _, _) in self.surfaces.items():
            self.assert_protected_choices_empty(
                self.form(surface, self.payload(surface))
            )
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 403)
            self.assert_safe_body(response, keys=("A", "B", "C", "D", "X"))

    def test_revoked_role_cannot_enter_any_affected_http_surface(self):
        self.membership.role_assignments.update(revoked_at=timezone.now())
        for route in [item[0] for item in self.surfaces.values()] + [
            "workforce:assignment_sites"
        ]:
            response = self.client.get(
                reverse(route), {"project": self.projects["A"].pk}
            )
            self.assertEqual(response.status_code, 403)
            self.assert_safe_body(response)

    def test_site_only_grant_does_not_expand_po_authority(self):
        self.site_only_scope()
        for surface in ("daily", "equipment", "workforce"):
            form = self.form(surface, self.payload(surface))
            self.assert_project_choices(form, keys=("A",))
            self.assertSetEqual(set(form.fields["site"].queryset), {self.sites["A"]})
            self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertSetEqual(
            set(self.form("daily").fields["phase"].queryset), {self.phases["A"]}
        )
        self.assert_protected_choices_empty(self.form("order", self.payload("order")))
        response = self.client.get(reverse("procurement:order_create"))
        self.assertEqual(response.status_code, 200)
        self.assert_safe_body(response, keys=("B", "C", "D", "X"))
        # The shared context selector may show the granted site's parent A.
        # PO's own project/request fields must not turn that into PO authority.
        self.assertNotIn(
            str(self.projects["A"].pk), str(response.context["form"]["project"])
        )
        self.assertNotContains(response, str(self.requests["A"].pk))
        self.assertNotContains(response, self.requests["A"].request_number)
        response = self.client.post(
            reverse("procurement:order_create"), self.payload("order")
        )
        self.assertIn("project", response.context["form"].errors)
        self.assertFalse(PurchaseOrder.objects.exists())
        self.assert_safe_body(response, keys=("B", "C", "D", "X"))
        self.assertNotContains(response, str(self.requests["A"].pk))

    def test_site_only_grant_rejects_sibling_site_and_phase(self):
        self.site_only_scope()
        for surface in ("daily", "equipment", "workforce"):
            data = self.payload(surface) | {"site": str(self.sibling_site.pk)}
            response = self.client.post(reverse(self.surfaces[surface][0]), data)
            self.assertIn("site", response.context["form"].errors)
            self.assertNotContains(response, self.sibling_site.name)
            self.assertNotContains(response, str(self.sibling_site.pk))
        form = self.form(
            "daily", self.payload("daily") | {"phase": str(self.sibling_phase.pk)}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("phase", form.errors)

    def test_workforce_endpoint_returns_authorized_a_and_b_sites(self):
        for key in ("A", "B"):
            response = self.client.get(
                reverse("workforce:assignment_sites"),
                {"project": self.projects[key].pk},
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, str(self.sites[key].pk))
            self.assertContains(response, self.sites[key].name)
            self.assert_safe_body(response)

    def test_workforce_endpoint_never_discloses_c_d_or_cross_tenant(self):
        for key in ("C", "D", "X"):
            response = self.client.get(
                reverse("workforce:assignment_sites"),
                {"project": self.projects[key].pk},
            )
            self.assertEqual(response.status_code, 200)
            self.assert_safe_body(response)
            self.assertEqual(response.content.decode().count("<option"), 1)

    def test_workforce_endpoint_handles_missing_and_malformed_parent_safely(self):
        for value in ("", "not-a-uuid", "1", "<script>"):
            response = self.client.get(
                reverse("workforce:assignment_sites"), {"project": value}
            )
            self.assertEqual(response.status_code, 200)
            self.assert_safe_body(response, keys=("A", "B", "C", "D", "X"))

    def test_workforce_endpoint_site_only_grant_excludes_sibling_sites(self):
        self.site_only_scope()
        response = self.client.get(
            reverse("workforce:assignment_sites"), {"project": self.projects["A"].pk}
        )
        self.assertContains(response, str(self.sites["A"].pk))
        self.assertNotContains(response, str(self.sibling_site.pk))
        self.assertNotContains(response, self.sibling_site.name)
        self.assert_safe_body(response)

    def test_direct_project_reads_still_deny_unauthorized_objects(self):
        for key in ("C", "D", "X"):
            response = self.client.get(
                reverse("projects:detail", kwargs={"project_id": self.projects[key].pk})
            )
            self.assertIn(response.status_code, (403, 404))
            self.assert_safe_body(response, supplied_project=self.projects[key])

    def test_global_project_search_still_excludes_unauthorized_objects(self):
        response = self.client.get(reverse("global_search"), {"q": "F111"})
        self.assertEqual(response.status_code, 200)
        for key in ("A", "B"):
            self.assertContains(response, self.projects[key].name)
        self.assert_safe_body(response)

    def test_shared_context_options_remain_scoped(self):
        for source, field in (
            ("expenses", "phase"),
            ("estimates", "phase"),
            ("estimates", "contract"),
        ):
            for key in ("A", "B", "C", "D", "X"):
                response = self.client.get(
                    reverse("organizations:form_context_options"),
                    {
                        "source": source,
                        "field": field,
                        "project": self.projects[key].pk,
                    },
                )
                self.assertEqual(response.status_code, 200)
                if key in ("C", "D", "X"):
                    self.assertEqual(response.json(), {"options": []})
                else:
                    record = (
                        self.phases[key] if field == "phase" else self.contracts[key]
                    )
                    self.assertIn(
                        str(record.pk),
                        {option["value"] for option in response.json()["options"]},
                    )
                self.assert_safe_body(response)

    def test_known_good_expense_and_estimate_forms_preserve_both_parent_choices(self):
        membership = get_active_membership(
            user=self.user, organization=self.organization
        )
        for form_class in (ExpenseForm, EstimateForm):
            for key in ("A", "B"):
                form = form_class(
                    organization=self.organization,
                    membership=membership,
                    active_project=self.projects[key],
                )
                self.assert_project_choices(form)
                self.assertIn(self.phases[key], form.fields["phase"].queryset)
                self.assertNotIn(self.phases["C"], form.fields["phase"].queryset)
                bound = form_class(
                    data={"project": self.projects[key].pk},
                    organization=self.organization,
                    membership=membership,
                )
                self.assertIn(self.phases[key], bound.fields["phase"].queryset)

    def test_known_good_expense_and_estimate_http_forms_remain_scoped(self):
        for route in ("expenses:create", "estimates:create"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assert_project_choices(response.context["form"])
            self.assert_safe_body(response)
            response = self.client.post(
                reverse(route), {"project": str(self.projects["B"].pk)}
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assert_project_choices(response.context["form"])
            self.assertIn(
                self.phases["B"], response.context["form"].fields["phase"].queryset
            )
            self.assert_safe_body(response)

    def test_mutation_services_still_reject_unauthorized_same_and_cross_tenant(self):
        for key in ("C", "D", "X"):
            for surface in self.surfaces:
                with self.subTest(project=key, surface=surface):
                    model = self.surfaces[surface][2]
                    before = model.objects.count()
                    with self.assertRaises(PermissionDenied):
                        self.call_service(surface, key)
                    self.assertEqual(model.objects.count(), before)

    def call_service(self, surface, key):
        common = {
            "organization": self.organization,
            "actor": self.user,
            "project": self.projects[key],
        }
        if surface == "daily":
            return create_daily_report(
                **common,
                site=self.sites[key],
                phase=self.phases[key],
                reporting_date=timezone.localdate(),
                work_performed="F111 service test",
            )
        if surface == "equipment":
            return assign_equipment(
                **common,
                equipment=self.equipment,
                site=self.sites[key],
                start_date=timezone.localdate(),
            )
        if surface == "order":
            return create_purchase_order(
                **common,
                supplier=self.supplier,
                purchase_request=self.requests[key],
                order_number="F111-SERVICE",
                order_date=timezone.localdate(),
            )
        return assign_employee_to_project(
            **common,
            employee=self.employee,
            site=self.sites[key],
            start_date=timezone.localdate(),
        )

    def test_site_only_grant_preserves_service_specific_authorization(self):
        self.site_only_scope()
        self.call_service("daily", "A")
        self.call_service("equipment", "A")
        for surface in ("order", "workforce"):
            with self.assertRaises(PermissionDenied):
                self.call_service(surface, "A")

    def test_valid_authorized_b_posts_succeed_for_three_project_scoped_services(self):
        for surface in ("daily", "equipment", "order"):
            route, _, model = self.surfaces[surface]
            response = self.client.post(reverse(route), self.payload(surface, "B"))
            self.assertEqual(
                response.status_code,
                302,
                response.context["form"].errors.as_json() if response.context else "",
            )
            self.assertTrue(model.objects.filter(project=self.projects["B"]).exists())

    def test_workforce_scoped_post_preserves_existing_organization_service_gate(self):
        response = self.client.post(
            reverse("workforce:assignment_create"), self.payload("workforce", "B")
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(EmployeeProjectAssignment.objects.exists())
        self.assert_safe_body(response)

    def test_workforce_organization_grant_preserves_existing_success_path(self):
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="F111 isolated organization-scope control",
        )
        response = self.client.post(
            reverse("workforce:assignment_create"), self.payload("workforce", "B")
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EmployeeProjectAssignment.objects.filter(
                project=self.projects["B"]
            ).exists()
        )

    def test_existing_approved_request_and_project_lifecycle_filters_are_preserved(
        self,
    ):
        self.requests["A"].status = PurchaseRequestStatus.DRAFT
        self.requests["A"].save(update_fields=["status"])
        self.assertSetEqual(
            set(self.form("order").fields["purchase_request"].queryset),
            {self.requests["B"]},
        )
        self.projects["A"].deleted_at = timezone.now()
        self.projects["A"].save(update_fields=["deleted_at"])
        for surface in self.surfaces:
            self.assert_project_choices(self.form(surface), keys=("B",))
        self.assertNotIn(self.sites["A"], self.form("daily").fields["site"].queryset)
        self.assertNotIn(self.phases["A"], self.form("daily").fields["phase"].queryset)

    def test_inactive_sites_and_phases_remain_excluded(self):
        self.sites["A"].is_active = False
        self.sites["A"].save(update_fields=["is_active"])
        for surface in ("daily", "equipment", "workforce"):
            self.assertNotIn(
                self.sites["A"],
                self.form(surface, self.payload(surface)).fields["site"].queryset,
            )
        self.assertNotIn(self.phases["A"], self.form("daily").fields["phase"].queryset)
        self.phases["B"].status = ProjectPhaseStatus.COMPLETED
        self.phases["B"].save(update_fields=["status"])
        self.assertNotIn(self.phases["B"], self.form("daily").fields["phase"].queryset)
