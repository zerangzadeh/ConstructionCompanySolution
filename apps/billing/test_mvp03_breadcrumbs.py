"""Business breadcrumb destinations obey existing source scope and exposure."""

from html.parser import HTMLParser

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.models import ProgressRecord
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.services import create_estimate
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.projects.models import Project


class BreadcrumbMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.current = []
        self.last = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"a", "span"}:
            self.last = tag
        if tag == "a":
            self.links.append(attrs.get("href"))
        if attrs.get("aria-current") == "page":
            self.current.append(tag)


def breadcrumb_markup(response):
    html = (
        response.content.decode()
        .split('aria-label="مسیر صفحه">', 1)[1]
        .split("</nav>", 1)[0]
    )
    return BreadcrumbMarkup(html)


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class SharedBreadcrumbTests(SimpleTestCase):
    def test_parent_exposure_and_final_non_link_even_when_current_has_url(self):
        html = render_to_string(
            "components/page_header.html",
            {
                "page_title": "صفحه جاری",
                "page_breadcrumbs": [
                    {"label": "خانه", "url": reverse("home")},
                    {"label": "پروژه‌ها", "url": reverse("projects:list")},
                    {"label": "گروه مفهومی", "url": ""},
                    {"label": "پنهان", "url": "/payroll/"},
                    {"label": "نامعتبر", "url": "#"},
                    {"label": "صفحه جاری", "url": reverse("projects:create")},
                ],
            },
        )
        markup = BreadcrumbMarkup(html)
        self.assertEqual(markup.links, [reverse("home"), reverse("projects:list")])
        self.assertEqual(markup.current, ["span"])
        self.assertEqual(markup.last, "span")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BusinessBreadcrumbTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def assert_trail(self, url, parents=(), absent=()):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        markup = breadcrumb_markup(response)
        self.assertEqual(markup.current, ["span"])
        self.assertEqual(markup.last, "span")
        self.assertNotIn("#", markup.links)
        for parent in parents:
            self.assertIn(parent, markup.links)
        for parent in absent:
            self.assertNotIn(parent, markup.links)
        return response

    def test_project_estimate_contract_context_and_back_destination(self):
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="BC-E",
            title="برآورد مسیر",
        )
        project = reverse("projects:detail", args=[self.project.pk])
        detail = reverse("estimates:detail", args=[estimate.pk])
        for route in ("estimates:create", "contracts:create"):
            self.assert_trail(reverse(route) + f"?project={self.project.pk}", [project])
        response = self.assert_trail(detail, [project, reverse("estimates:list")])
        target = response.context["related_contract_url"]
        self.assertEqual(
            target,
            reverse("contracts:detail", args=[self.contract.pk])
            + f"?estimate={estimate.pk}",
        )
        self.assert_trail(target, [project, detail, reverse("contracts:list")])
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_claim_baseline_progress_details_lists_and_create_have_real_parents(self):
        claim = self._claim()
        record = ProgressRecord.objects.get(baseline=claim.baseline)
        project = reverse("projects:detail", args=[self.project.pk])
        contract = reverse("contracts:detail", args=[self.contract.pk])
        for route, identifier, collection in (
            ("billing:baseline_detail", claim.baseline.pk, "billing:baseline_list"),
            ("billing:progress_detail", record.pk, "billing:progress_list"),
            ("billing:claim_detail", claim.pk, "billing:claim_list"),
        ):
            self.assert_trail(
                reverse(route, args=[identifier]),
                [project, contract, reverse(collection)],
            )
        for route in (
            "billing:baseline_list",
            "billing:progress_list",
            "billing:claim_list",
        ):
            self.assert_trail(
                reverse(route) + f"?contract={self.contract.pk}", [project, contract]
            )
        self.assert_trail(
            reverse("billing:claim_create") + f"?contract={self.contract.pk}",
            [project, contract, reverse("billing:claim_list")],
        )

    def test_forged_foreign_or_unrelated_estimate_never_becomes_breadcrumb_parent(self):
        other_org = Organization.objects.create(
            name="Private tenant", slug="bc-private"
        )
        other_project = Project.objects.create(
            organization=other_org, code="PRIVATE", name="پروژه محرمانه"
        )
        from apps.estimates.models import Estimate

        private = Estimate.objects.create(
            organization=other_org,
            project=other_project,
            estimate_number="PRIVATE",
            title="برآورد محرمانه",
        )
        unrelated = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="BC-UNLINK",
            title="برآورد نامرتبط",
        )
        detail = reverse("contracts:detail", args=[self.contract.pk])
        for value in (private.pk, unrelated.pk, "invalid"):
            response = self.assert_trail(
                detail + f"?estimate={value}",
                absent=[
                    reverse("estimates:detail", args=[private.pk]),
                    reverse("estimates:detail", args=[unrelated.pk]),
                ],
            )
            self.assertNotContains(response, private.title)
        for route in (
            "billing:baseline_list",
            "billing:progress_list",
            "billing:claim_list",
        ):
            self.assert_trail(
                reverse(route) + "?contract=00000000-0000-0000-0000-000000000001",
                absent=[detail],
            )

    def test_parent_permissions_and_scope_remain_independent_of_child_access(self):
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="BC-SCOPED",
            title="برآورد مجاز",
        )
        actor = User.objects.create_user(username="breadcrumb-contract-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="bc-reader", name="خواننده قرارداد"
        )
        role.permissions.add(BusinessPermission.objects.get(code="contracts.view"))
        member = self.organization.memberships.create(
            user=actor, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=role,
            reason="Explicit breadcrumb test role",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=self.project,
            reason="Explicit test scope",
        )
        self.login(actor)
        project = reverse("projects:detail", args=[self.project.pk])
        estimate_url = reverse("estimates:detail", args=[estimate.pk])
        detail = (
            reverse("contracts:detail", args=[self.contract.pk])
            + f"?estimate={estimate.pk}"
        )
        self.assert_trail(detail, [reverse("contracts:list")], [project, estimate_url])
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=("projects.view", "estimates.view")
            )
        )
        self.assert_trail(detail, [project, estimate_url])
        other = Project.objects.create(
            organization=self.organization, code="BC-SCOPE", name="پروژه دیگر"
        )
        grant.project = other
        grant.save()
        self.assertEqual(self.client.get(detail).status_code, 404)
