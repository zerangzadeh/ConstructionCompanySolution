from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project, ProjectSite


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class SiteDetailPresentationTests(SimpleTestCase):
    def setUp(self):
        self.project = SimpleNamespace(pk=UUID(int=1), name="پروژه نمونه")
        self.site = SimpleNamespace(
            pk=UUID(int=2),
            project=self.project,
            project_id=self.project.pk,
            name="کارگاه نمونه",
            code="SITE-01",
            address="نشانی نمونه کارگاه",
            is_active=True,
        )
        path = reverse("projects:site_detail", args=[self.project.pk, self.site.pk])
        self.request = RequestFactory().get(path)
        self.request.user = AnonymousUser()
        self.request.organization = None
        self.request.resolver_match = resolve(path)

    def render_detail(self, permissions=()):
        with patch(
            "apps.workforce.templatetags.field_journey.has_business_permission",
            side_effect=lambda **context: context["permission"] in permissions,
        ) as permission_check:
            page = render_to_string(
                "projects/site_detail.html",
                {"request": self.request, "site": self.site},
            )
        for permission in ("employees.view", "attendance.view"):
            permission_check.assert_any_call(
                user=self.request.user,
                organization=self.request.organization,
                permission=permission,
                project=self.project,
                site=self.site,
                allow_site_parent=True,
            )
        return page.split('<article class="erp-record-detail"', 1)[1].split(
            "</article>", 1
        )[0]

    def test_overview_displays_existing_site_fields_once(self):
        overview = self.render_detail()
        self.assertIn("اطلاعات و وضعیت کارگاه پروژه", overview)
        self.assertIn(reverse("projects:site_list", args=[self.project.pk]), overview)
        self.assertIn('aria-label="خلاصه کارگاه"', overview)
        self.assertEqual(overview.count('class="erp-record-summary__item"'), 4)
        self.assertInHTML('<bdi dir="ltr">SITE-01</bdi>', overview, count=1)
        self.assertEqual(overview.count(self.project.name), 1)
        self.assertEqual(overview.count(self.site.address), 1)
        self.assertIn(">فعال</span>", overview)

        self.site.is_active = False
        self.site.address = ""
        overview = self.render_detail()
        self.assertIn(">غیرفعال</span>", overview)
        self.assertInHTML("<dd>—</dd>", overview, count=1)

    def test_header_actions_preserve_scope_and_emphasize_first_available_link(self):
        query = f"project={self.project.pk}&amp;site={self.site.pk}"
        workforce = f"{reverse('workforce:field_list')}?{query}"
        timekeeping = f"{reverse('timekeeping:workbench')}?{query}"
        for permissions, primary, secondary, hidden in (
            (("employees.view", "attendance.view"), workforce, timekeeping, ()),
            (("employees.view",), workforce, None, (timekeeping,)),
            (("attendance.view",), timekeeping, None, (workforce,)),
            ((), None, None, (workforce, timekeeping)),
        ):
            with self.subTest(permissions=permissions):
                detail = self.render_detail(permissions)
                for button, url in (("primary", primary), ("secondary", secondary)):
                    if url:
                        link = f'class="erp-btn erp-btn--{button}" href="{url}"'
                        self.assertEqual(detail.count(link), 1)
                for url in hidden:
                    self.assertNotIn(url, detail)
                if not primary:
                    self.assertNotIn("erp-record-journeys", detail)

    def test_existing_journey_callers_keep_secondary_actions(self):
        with patch(
            "apps.workforce.templatetags.field_journey.has_business_permission",
            return_value=True,
        ):
            actions = Template(
                "{% load field_journey %}{% field_journey project site %}"
            ).render(
                Context(
                    {
                        "request": self.request,
                        "project": self.project,
                        "site": self.site,
                    }
                )
            )
        self.assertEqual(actions.count("erp-btn--secondary"), 2)
        self.assertNotIn("erp-btn--primary", actions)
        self.assertNotIn("<svg", actions)
        self.assertIn('aria-label="عملیات نیروی کار"', actions)


class SiteDetailBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = User.objects.create_user(username="site-detail-reader")
        cls.unscoped = User.objects.create_user(username="site-detail-unscoped")
        cls.organization = Organization.objects.create(
            name="Site tenant", slug="site-qa"
        )
        foreign = Organization.objects.create(name="Foreign tenant", slug="site-other")
        cls.project = Project.objects.create(
            organization=cls.organization, code="VISIBLE", name="Visible project"
        )
        other_project = Project.objects.create(
            organization=cls.organization, code="HIDDEN", name="Hidden project"
        )
        foreign_project = Project.objects.create(
            organization=foreign, code="FOREIGN", name="Foreign project"
        )
        cls.site = ProjectSite.objects.create(
            organization=cls.organization,
            project=cls.project,
            code="VISIBLE-SITE",
            name="Visible site",
        )
        cls.hidden_site = ProjectSite.objects.create(
            organization=cls.organization,
            project=other_project,
            code="HIDDEN-SITE",
            name="Hidden site",
        )
        cls.foreign_site = ProjectSite.objects.create(
            organization=foreign,
            project=foreign_project,
            code="FOREIGN-SITE",
            name="Foreign site",
        )
        for user in (cls.reader, cls.unscoped):
            membership = cls.organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.ACTIVE,
            )
            if user == cls.reader:
                MembershipScopeGrant.objects.create(
                    organization=cls.organization,
                    membership=membership,
                    scope_type=AuthorizationScopeType.PROJECT,
                    project=cls.project,
                    reason="Site detail boundary fixture",
                )

    def setUp(self):
        self.client.force_login(self.reader)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def test_site_detail_is_get_only_and_renders_the_authorized_record(self):
        url = reverse("projects:site_detail", args=[self.project.pk, self.site.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "projects/site_detail.html")
        self.assertContains(response, self.site.name)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.hidden_site.name)
        self.assertNotContains(response, self.foreign_site.name)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_direct_site_urls_reject_foreign_hidden_and_mismatched_records(self):
        for project_id, site_id in (
            (self.hidden_site.project_id, self.hidden_site.pk),
            (self.foreign_site.project_id, self.foreign_site.pk),
            (self.hidden_site.project_id, self.site.pk),
        ):
            with self.subTest(project=project_id, site=site_id):
                response = self.client.get(
                    reverse("projects:site_detail", args=[project_id, site_id])
                )
                self.assertEqual(response.status_code, 404)

    def test_site_detail_denies_members_without_scope(self):
        self.client.force_login(self.unscoped)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("projects:site_detail", args=[self.project.pk, self.site.pk])
        )
        self.assertEqual(response.status_code, 403)
