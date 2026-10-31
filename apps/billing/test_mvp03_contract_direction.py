"""Contract billing entry points reuse existing receivable Create rules."""

from uuid import uuid4

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.projects.models import Project

from .test_mvp03 import JourneyFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractDirectionTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)
        self.list_url = reverse("billing:claim_list")
        self.detail_url = reverse("contracts:detail", args=[self.contract.pk])
        self.create_url = (
            reverse("billing:claim_create") + f"?contract={self.contract.pk}"
        )

    def test_receivable_contract_and_contextual_list_create_resolve(self):
        self._approved_baseline()
        before = dict(self.client.session)
        for url in (self.detail_url, self.list_url + f"?contract={self.contract.pk}"):
            response = self.client.get(url)
            self.assertContains(response, f'href="{self.create_url}"')
            self.assertEqual(self.client.get(self.create_url).status_code, 200)
        self.assertEqual(dict(self.client.session), before)

    def test_payable_has_no_receivable_billing_links_or_create_cta(self):
        Contract.objects.filter(pk=self.contract.pk).update(direction="payable")
        detail = self.client.get(self.detail_url)
        for route in ("claim_create", "claim_list", "baseline_list"):
            self.assertNotContains(
                detail,
                f'href="{reverse("billing:" + route)}?contract={self.contract.pk}"',
            )
        response = self.client.get(self.list_url, {"contract": self.contract.pk})
        self.assertFalse(response.context["can_create_claim"])
        self.assertEqual(response.context["create_url"], "")
        self.assertNotContains(response, "صورت‌وضعیت جدید")
        # Existing server-side direction guard is preserved.
        self.assertEqual(self.client.get(self.create_url).status_code, 404)

    def test_inactive_contracts_do_not_generate_dead_create_links(self):
        for status in ("draft", "closed", "terminated"):
            with self.subTest(status=status):
                Contract.objects.filter(pk=self.contract.pk).update(status=status)
                for url in (
                    self.detail_url,
                    self.list_url + f"?contract={self.contract.pk}",
                ):
                    self.assertNotContains(self.client.get(url), self.create_url)

    def test_invalid_empty_missing_and_ambiguous_context_never_fall_back_to_create(
        self,
    ):
        for value in (
            "",
            "invalid",
            str(uuid4()),
            [self.contract.pk, self.contract.pk],
        ):
            with self.subTest(value=value):
                response = self.client.get(self.list_url, {"contract": value})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["can_create_claim"])
                self.assertEqual(response.context["create_url"], "")
                self.assertNotContains(response, "صورت‌وضعیت جدید")

    def test_foreign_contract_is_not_exposed_or_offered_for_creation(self):
        foreign = Organization.objects.create(name="Foreign", slug="direction-other")
        project = Project.objects.create(
            organization=foreign, code="OTHER", name="Other"
        )
        contract = Contract.objects.create(
            organization=foreign,
            project=project,
            contract_number="OTHER",
            title="Foreign private contract",
            counterparty_name="Synthetic foreign party",
            direction="receivable",
            status="active",
        )
        response = self.client.get(self.list_url, {"contract": contract.pk})
        self.assertFalse(response.context["can_create_claim"])
        self.assertIsNone(response.context["selected_contract"])
        self.assertNotContains(response, contract.title)

    def test_deleted_project_suppresses_contextual_create(self):
        Project.objects.filter(pk=self.project.pk).update(deleted_at=timezone.now())
        response = self.client.get(self.list_url, {"contract": self.contract.pk})
        self.assertFalse(response.context["can_create_claim"])

    def test_contract_filters_ignore_irrelevant_search_and_retain_context(self):
        claim = self._claim()
        query = {"contract": self.contract.pk, "q": "cannot-match", "status": "draft"}
        response = self.client.get(self.list_url, query)
        self.assertContains(response, reverse("billing:claim_detail", args=[claim.pk]))
        self.assertNotContains(response, 'id="claim-search"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, f'name="contract" value="{self.contract.pk}"')
        self.assertEqual(
            response.context["clear_filters_url"],
            self.list_url + f"?contract={self.contract.pk}",
        )
        self.assertContains(response, self.contract.title)
        response = self.client.get(self.list_url, {**query, "status": "approved"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_direct_list_keeps_search_and_general_create(self):
        response = self.client.get(self.list_url)
        self.assertTrue(response.context["can_create_claim"])
        self.assertContains(response, 'id="claim-search"')
        self.assertEqual(
            response.context["create_url"], reverse("billing:claim_create")
        )
        self.assertEqual(
            self.client.get(response.context["create_url"]).status_code, 200
        )

    def test_existing_missing_baseline_guidance_is_preserved(self):
        response = self.client.get(self.list_url, {"contract": self.contract.pk})
        self.assertTrue(response.context["can_create_claim"])
        response = self.client.get(response.context["create_url"])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].no_eligible_baseline)

    def test_permission_and_project_scope_are_required_for_contextual_cta(self):
        from apps.accounts.models import User

        actor = User.objects.create_user(username="direction-scoped")
        codes = (
            "claims.view",
            "claims.create",
            "claims.revise",
            "contracts.view",
            "baselines.view",
        )
        role = OrganizationRole.objects.create(
            organization=self.organization, code="direction", name="Direction test"
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=codes))
        membership = self.organization.memberships.create(
            user=actor, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit test role",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="organization",
            reason="Explicit test scope",
        )
        self.login(actor)
        self.assertTrue(
            self.client.get(self.list_url, {"contract": self.contract.pk}).context[
                "can_create_claim"
            ]
        )
        # Create retains its existing organization-level permission requirements.
        for code in codes[1:]:
            permission = BusinessPermission.objects.get(code=code)
            role.permissions.remove(permission)
            response = self.client.get(self.list_url, {"contract": self.contract.pk})
            self.assertFalse(response.context["can_create_claim"])
            role.permissions.add(permission)
        other = Project.objects.create(
            organization=self.organization, code="OUT", name="Out"
        )
        grant.scope_type = "project"
        grant.project = other
        grant.save()
        response = self.client.get(self.list_url, {"contract": self.contract.pk})
        self.assertIsNone(response.context["selected_contract"])
        self.assertFalse(response.context["can_create_claim"])
