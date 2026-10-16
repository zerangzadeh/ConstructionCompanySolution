"""CEP-016 persistent context and scoped-form acceptance evidence."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.expenses.forms import ExpenseForm
from apps.organizations.authorization import get_active_membership
from apps.organizations.context import (
    ACTIVE_PROJECT_SESSION_KEY,
    ACTIVE_SITE_SESSION_KEY,
)
from apps.organizations.models import AuthorizationScopeType, MembershipScopeGrant
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.projects.models import Project, ProjectPhase, ProjectSite


class CEP016ContextTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="cep016-owner", password="test-password"
        )
        self.other_user = User.objects.create_user(
            username="cep016-other", password="test-password"
        )
        self.organization = create_organization_with_owner(
            owner=self.user, name="شرکت دامنه", slug="cep016-company"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_user, name="شرکت حفاظت‌شده", slug="cep016-protected"
        )
        self.project = Project.objects.create(
            organization=self.organization, code="P-016", name="پروژه مجاز"
        )
        self.sibling = Project.objects.create(
            organization=self.organization, code="P-HIDDEN", name="پروژه غیرمجاز"
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="P-OTHER",
            name="پروژه شرکت دیگر",
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="S-016",
            name="کارگاه مجاز",
        )
        self.sibling_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.sibling,
            code="S-HIDDEN",
            name="کارگاه غیرمجاز",
        )
        self.phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="PH-016",
            name="فاز مجاز",
        )
        self.membership = get_active_membership(
            user=self.user, organization=self.organization
        )
        self.membership.scope_grants.all().delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="CEP-016 bounded project fixture",
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def test_valid_project_and_site_context_persist_and_render_in_rtl_shell(
        self,
    ) -> None:
        response = self.client.post(
            reverse("organizations:update_context"),
            {
                "project_id": self.project.pk,
                "site_id": self.site.pk,
                "next": reverse("home"),
            },
        )
        self.assertRedirects(response, reverse("home"))
        session = self.client.session
        self.assertEqual(session[ACTIVE_PROJECT_SESSION_KEY], str(self.project.pk))
        self.assertEqual(session[ACTIVE_SITE_SESSION_KEY], str(self.site.pk))

        response = self.client.get(reverse("home"))
        self.assertContains(response, '<html lang="fa" dir="rtl">')
        self.assertContains(response, "دامنه کاری مؤثر")
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.sibling.name)
        self.assertNotContains(response, self.other_project.name)

    def test_project_change_resets_site_and_blank_project_clears_both(self) -> None:
        session = self.client.session
        session[ACTIVE_PROJECT_SESSION_KEY] = str(self.project.pk)
        session[ACTIVE_SITE_SESSION_KEY] = str(self.site.pk)
        session.save()

        response = self.client.post(
            reverse("organizations:update_context"),
            {"project_id": self.project.pk, "site_id": "", "next": "/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(ACTIVE_SITE_SESSION_KEY, self.client.session)

        self.client.post(
            reverse("organizations:update_context"),
            {"project_id": "", "site_id": "", "next": "/"},
        )
        self.assertNotIn(ACTIVE_PROJECT_SESSION_KEY, self.client.session)
        self.assertNotIn(ACTIVE_SITE_SESSION_KEY, self.client.session)

    def test_stale_session_context_is_invalidated_by_middleware(self) -> None:
        session = self.client.session
        session[ACTIVE_PROJECT_SESSION_KEY] = str(self.sibling.pk)
        session[ACTIVE_SITE_SESSION_KEY] = str(self.sibling_site.pk)
        session.save()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(ACTIVE_PROJECT_SESSION_KEY, self.client.session)
        self.assertNotIn(ACTIVE_SITE_SESSION_KEY, self.client.session)
        self.assertNotContains(response, self.sibling.name)

    def test_context_route_rejects_unauthorized_and_cross_tenant_ids_without_leak(
        self,
    ) -> None:
        for project_id in (self.sibling.pk, self.other_project.pk):
            response = self.client.post(
                reverse("organizations:update_context"),
                {"project_id": project_id, "next": "/"},
            )
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, "دامنه انتخاب‌شده مجاز نیست.", status_code=403)
            self.assertNotContains(response, self.other_project.name, status_code=403)

    def test_context_open_redirect_is_rejected(self) -> None:
        response = self.client.post(
            reverse("organizations:update_context"),
            {
                "project_id": self.project.pk,
                "next": "https://attacker.example/redirect",
            },
        )
        self.assertRedirects(response, reverse("home"))

    def test_expense_form_choices_intersect_scope_and_parent_context(self) -> None:
        form = ExpenseForm(
            organization=self.organization,
            membership=self.membership,
            active_project=self.project,
        )
        self.assertEqual(list(form.fields["project"].queryset), [self.project])
        self.assertEqual(list(form.fields["phase"].queryset), [self.phase])
        self.assertEqual(form.initial["project"], self.project.pk)
        self.assertIn("data-cascade-project", form.fields["project"].widget.attrs)
        self.assertEqual(
            form.fields["phase"].widget.attrs["data-cascade-source"], "expenses"
        )

    def test_bound_stale_project_and_phase_are_rejected_server_side(self) -> None:
        form = ExpenseForm(
            data={"project": self.sibling.pk, "phase": self.phase.pk},
            organization=self.organization,
            membership=self.membership,
            active_project=self.project,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("project", form.errors)
        self.assertIn("phase", form.errors)

    def test_cascade_endpoint_returns_only_authorized_parent_choices(self) -> None:
        allowed = self.client.get(
            reverse("organizations:form_context_options"),
            {"source": "expenses", "field": "phase", "project": self.project.pk},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed.json()["options"],
            [
                {
                    "value": str(self.phase.pk),
                    "label": f"{self.site.name} — {self.phase.name}",
                }
            ],
        )

        denied = self.client.get(
            reverse("organizations:form_context_options"),
            {"source": "expenses", "field": "phase", "project": self.sibling.pk},
        )
        self.assertEqual(denied.status_code, 200)
        self.assertEqual(denied.json(), {"options": []})

        malformed = self.client.get(
            reverse("organizations:form_context_options"),
            {"source": "expenses", "field": "phase", "project": "not-a-uuid"},
        )
        self.assertEqual(malformed.status_code, 200)
        self.assertEqual(malformed.json(), {"options": []})

    def test_mutation_surface_explains_context_is_not_authority(self) -> None:
        session = self.client.session
        session[ACTIVE_PROJECT_SESSION_KEY] = str(self.project.pk)
        session.save()
        response = self.client.get(reverse("expenses:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پروژه مؤثر این ثبت")
        self.assertContains(response, "مجوز تازه‌ای ایجاد نمی‌کند")
        self.assertContains(response, "برای این عملیات الزامی")
        self.assertNotContains(response, self.sibling.name)
