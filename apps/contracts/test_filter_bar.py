"""Contract List filtering stays inside the existing scoped read boundary."""

from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractFilterTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)
        self.url = reverse("contracts:list")
        self.project.name = "پروژه پل ساحلی"
        self.project.save()
        self.payable = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            party=self.party,
            contract_number="SIDE-2026",
            title="اجرای دیوار ساحلی",
            counterparty_name="تأمین‌کننده نمونه",
            direction="payable",
            status="draft",
        )

    def test_general_list_has_one_search_compact_filters_and_business_side_labels(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["filter_bar"]["result_count"], 2)
        for text in (
            "جست‌وجوی قرارداد",
            "سمت قرارداد",
            "با کارفرما",
            "با پیمانکار / تأمین‌کننده",
            "فیلترهای بیشتر",
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'name="project"')
        self.assertNotContains(response, 'id="table-filters-row"')
        self.assertNotContains(response, "جهت قرارداد")

    def test_business_search_covers_each_requested_source(self):
        self.party.display_name = "طرف به‌روزشده آزمایشی"
        self.party.save()
        for term in (
            "SIDE-2026",
            "دیوار ساحلی",
            "پل ساحلی",
            "تأمین‌کننده نمونه",
            "طرف به‌روزشده آزمایشی",
        ):
            with self.subTest(term=term):
                response = self.client.get(self.url, {"q": term})
                self.assertIn(self.payable, response.context["contracts"])
        response = self.client.get(self.url, {"q": "cannot-match"})
        self.assertEqual(response.context["filter_bar"]["result_count"], 0)
        self.assertContains(response, "data-filter-bar")

    def test_combined_side_status_search_and_project_filters_intersect(self):
        query = {
            "q": "ساحلی",
            "status": "draft",
            "side": "payable",
            "project": self.project.pk,
        }
        response = self.client.get(self.url, query)
        self.assertEqual(response.context["contracts"], [self.payable])
        self.assertEqual(response.context["filter_bar"]["active_count"], 4)
        response = self.client.get(self.url, {**query, "side": "receivable"})
        self.assertEqual(response.context["contracts"], [])

    def test_project_context_has_no_duplicate_selector_and_survives_chip_clear(self):
        before = dict(self.client.session)
        response = self.client.get(
            self.url,
            {
                "project_id": self.project.pk,
                "side": "payable",
                "status": "draft",
                "project": "forged",
            },
        )
        self.assertEqual(response.context["contracts"], [self.payable])
        self.assertContains(response, f'name="project_id" value="{self.project.pk}"')
        self.assertNotContains(response, 'name="project"')
        self.assertContains(response, self.project.name)
        bar = response.context["filter_bar"]
        self.assertEqual(
            parse_qs(urlsplit(bar["clear_url"]).query),
            {"project_id": [str(self.project.pk)]},
        )
        for chip in bar["chips"]:
            query = parse_qs(urlsplit(chip["url"]).query)
            self.assertEqual(query["project_id"], [str(self.project.pk)])
            self.assertNotIn("project", query)
        self.assertEqual(dict(self.client.session), before)

    def test_legacy_bookmarked_filters_remain_secondary_and_removable(self):
        response = self.client.get(
            self.url, {"number": "SIDE", "title": "دیوار", "counterparty": "نمونه"}
        )
        self.assertEqual(response.context["contracts"], [self.payable])
        self.assertTrue(response.context["filter_bar"]["secondary_open"])
        self.assertEqual(response.context["filter_bar"]["active_count"], 3)

    def test_invalid_filters_do_not_broaden_results(self):
        for query in ({"project": "bad"}, {"status": "forged"}, {"side": "forged"}):
            with self.subTest(query=query):
                response = self.client.get(self.url, query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["contracts"], [])
                self.assertTrue(response.context["filter_bar"]["form"].errors)

    def test_project_choices_and_filter_deny_foreign_and_out_of_scope_projects(self):
        from apps.accounts.models import User

        foreign = Organization.objects.create(name="Other", slug="filters-foreign")
        foreign_project = Project.objects.create(
            organization=foreign, name="PRIVATE FOREIGN", code="OTHER"
        )
        Contract.objects.create(
            organization=foreign,
            project=foreign_project,
            contract_number="PRIVATE",
            title="PRIVATE CONTRACT",
            counterparty_name="Other",
        )
        for identifier in (foreign_project.pk,):
            response = self.client.get(self.url, {"project": identifier})
            self.assertEqual(response.context["contracts"], [])
        payload = self.client.get(self.url, {"filter_options": "project"}).json()
        self.assertNotIn(
            str(foreign_project.pk), [x["value"] for x in payload["results"]]
        )
        actor = User.objects.create_user(username="filter-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="filter-reader", name="مشاهده قرارداد"
        )
        role.permissions.add(BusinessPermission.objects.get(code="contracts.view"))
        membership = self.organization.memberships.create(
            user=actor, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit filter test",
        )
        other = Project.objects.create(
            organization=self.organization, code="SCOPE", name="Scoped only"
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="Explicit scope",
        )
        self.login(actor)
        self.assertEqual(
            self.client.get(self.url, {"filter_options": "project"}).json()["results"],
            [],
        )
        grant.project = self.project
        grant.save()
        # A Contracts viewer needs no new Create or Projects permission to filter
        # names already visible in their permitted Contract rows.
        payload = self.client.get(self.url, {"filter_options": "project"}).json()
        self.assertEqual(
            [x["value"] for x in payload["results"]], [str(self.project.pk)]
        )
        self.assertEqual(
            self.client.get(self.url, {"project": self.project.pk}).status_code, 200
        )
        role.permissions.clear()
        self.assertEqual(
            self.client.get(self.url, {"filter_options": "project"}).status_code, 403
        )

    def test_remote_options_paginate_and_pin_selected_projects_beyond_initial_window(
        self,
    ):
        projects = [
            Project(
                organization=self.organization,
                name=f"پروژه فیلتر {i:03}",
                code=f"FILTER-{i:03}",
            )
            for i in range(45)
        ]
        Project.objects.bulk_create(projects)
        Contract.objects.bulk_create(
            [
                Contract(
                    organization=self.organization,
                    project=p,
                    contract_number=f"FILTER-C-{i}",
                    title="فیلتر",
                    counterparty_name="نمونه",
                )
                for i, p in enumerate(projects)
            ]
        )
        response = self.client.get(self.url, {"filter_options": "project"})
        self.assertEqual(response["Cache-Control"], "private, no-store")
        payload = response.json()
        self.assertEqual(len(payload["results"]), 40)
        self.assertTrue(self.client.get(payload["next"]).json()["results"])
        target = projects[-1]
        payload = self.client.get(
            self.url, {"filter_options": "project", "q": "FILTER-044"}
        ).json()
        self.assertEqual([x["value"] for x in payload["results"]], [str(target.pk)])
        response = self.client.get(self.url, {"project": target.pk})
        self.assertContains(response, f'value="{target.pk}" selected')
