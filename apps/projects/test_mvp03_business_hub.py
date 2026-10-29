"""The project hub projects authorized sources and hands off to business pages."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.estimates.services import create_estimate
from apps.organizations.models import Organization
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProjectCommercialHubTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def test_summary_and_handoffs_are_bounded_to_project(self):
        claim = self._claim()
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="HUB-E",
            title="برآورد پروژه منتخب",
        )
        sibling = Project.objects.create(
            organization=self.organization, code="HUB-OTHER", name="پروژه دیگر"
        )
        Contract.objects.create(
            organization=self.organization,
            project=sibling,
            title="قرارداد پروژه دیگر",
            contract_number="HUB-OTHER",
            counterparty_name="Client",
        )
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        cards = response.context["commercial_summary"]
        self.assertEqual([card.total for card in cards], [1, 1, 1])
        self.assertEqual([card.state_count for card in cards], [1, 1, 0])
        self.assertEqual(
            cards[0].recent_url, reverse("estimates:detail", args=[estimate.pk])
        )
        self.assertEqual(
            cards[2].recent_url, reverse("billing:claim_detail", args=[claim.pk])
        )
        self.assertNotContains(response, "قرارداد پروژه دیگر")
        hub = (
            response.content.decode()
            .split('id="commercial-summary"')[1]
            .split("</section>")[0]
        )
        self.assertNotIn("<form", hub)
        self.assertNotIn("/submit/", hub)
        for card, route in zip(
            cards, ("estimates:list", "contracts:list", "billing:claim_list")
        ):
            self.assertEqual(
                card.list_url, reverse(route) + f"?project_id={self.project.pk}"
            )

    def test_dedicated_lists_and_create_actions_preserve_local_context(self):
        self._claim()
        create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="HUB-E",
            title="برآورد پروژه منتخب",
        )
        sibling = Project.objects.create(
            organization=self.organization, code="HUB-OTHER", name="پروژه دیگر"
        )
        session = self.client.session
        session["active_project_id"] = str(sibling.pk)
        session.save()
        before = dict(self.client.session)
        for route, key in (
            ("contracts:list", "contracts"),
            ("estimates:list", "estimates"),
            ("billing:claim_list", "claims"),
        ):
            with self.subTest(route=route):
                response = self.client.get(
                    reverse(route), {"project_id": self.project.pk}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["selected_project"], self.project)
                self.assertEqual(len(response.context[key]), 1)
                self.assertContains(response, 'name="project_id"')
                self.assertEqual(dict(self.client.session), before)
                empty = self.client.get(reverse(route), {"project_id": sibling.pk})
                self.assertEqual(len(empty.context[key]), 0)
        for route in ("contracts:create", "estimates:create"):
            response = self.client.get(reverse(route), {"project": self.project.pk})
            self.assertEqual(
                str(response.context["form"]["project"].value()), str(self.project.pk)
            )
            self.assertEqual(dict(self.client.session), before)

    def test_invalid_or_foreign_project_filter_never_falls_back_to_all_records(self):
        tenant = Organization.objects.create(name="Other tenant", slug="hub-other")
        foreign = Project.objects.create(
            organization=tenant, code="HUB-FOREIGN", name="پروژه محرمانه"
        )
        for route in ("contracts:list", "estimates:list", "billing:claim_list"):
            with self.subTest(route=route):
                self.assertEqual(
                    self.client.get(
                        reverse(route), {"project_id": "invalid"}
                    ).status_code,
                    404,
                )
                response = self.client.get(reverse(route), {"project_id": foreign.pk})
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "پروژه محرمانه", status_code=403)
        self.assertEqual(
            self.client.get(reverse("projects:detail", args=[foreign.pk])).status_code,
            403,
        )

    def test_independent_permissions_and_project_scope_hide_unauthorized_sources(self):
        from apps.accounts.models import User
        from apps.organizations.models import (
            BusinessPermission,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )

        reader = User.objects.create_user(username="hub-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="hub-reader", name="خواننده"
        )
        role.permissions.add(BusinessPermission.objects.get(code="projects.view"))
        member = self.organization.memberships.create(
            user=reader, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=role,
            reason="Explicit test role",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=self.project,
            reason="Explicit test scope",
        )
        self.login(reader)
        url = reverse("projects:detail", args=[self.project.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["commercial_summary"], ())
        self.assertNotContains(response, 'id="commercial-summary"')
        role.permissions.add(BusinessPermission.objects.get(code="contracts.view"))
        response = self.client.get(url)
        cards = response.context["commercial_summary"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].total, 1)
        self.assertFalse(cards[0].create_url)
        role.permissions.add(BusinessPermission.objects.get(code="contracts.create"))
        response = self.client.get(url)
        self.assertEqual(
            response.context["commercial_summary"][0].create_url,
            reverse("contracts:create") + f"?project={self.project.pk}",
        )
        self.assertEqual(
            self.client.get(
                reverse("contracts:create"), {"project": self.project.pk}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("contracts:list"), {"project_id": self.project.pk}
            ).status_code,
            200,
        )
        sibling = Project.objects.create(
            organization=self.organization, code="HUB-OTHER", name="پروژه دیگر"
        )
        grant.project = sibling
        grant.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("contracts:list"), {"project_id": self.project.pk}
            ).status_code,
            403,
        )
