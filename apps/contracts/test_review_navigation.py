"""Commercial-review navigation uses the same project boundary as its service."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project


class CommercialReviewNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="project-review-reader")
        cls.org = Organization.objects.create(
            name="Review tenant", slug="review-tenant"
        )
        cls.other = Organization.objects.create(
            name="Other tenant", slug="review-other"
        )
        cls.role = OrganizationRole.objects.create(
            organization=cls.org, code="review-reader", name="Review reader"
        )
        cls.role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=["contracts.view", "contractual_records.view"]
            )
        )
        cls.member = cls.org.memberships.create(
            user=cls.user,
            role_definition=cls.role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=cls.org,
            membership=cls.member,
            role=cls.role,
            reason="Explicit test assignment",
        )
        cls.projects = [
            Project.objects.create(organization=org, code=code, name=code)
            for org, code in [
                (cls.org, "assigned"),
                (cls.org, "hidden"),
                (cls.other, "foreign"),
            ]
        ]
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.member,
            scope_type="project",
            project=cls.projects[0],
            reason="Exact project test scope",
        )
        cls.contracts = [
            Contract.objects.create(
                organization=project.organization,
                project=project,
                contract_number=f"REVIEW-{index}",
                title="Reviewable contract",
                counterparty_name="Test counterparty",
                contract_value="1000.00",
            )
            for index, project in enumerate(cls.projects)
        ]

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def test_project_reader_sees_and_opens_review_without_organization_scope(self):
        detail = self.client.get(
            reverse("contracts:detail", args=[self.contracts[0].pk])
        )
        url = reverse("contracts:commercial_review", args=[self.contracts[0].pk])
        self.assertContains(detail, f'href="{url}"')
        self.assertContains(self.client.get(url), "خط زمانی و مقایسه تجاری قرارداد")

    def test_missing_review_permission_hides_link_and_denies_endpoint(self):
        self.role.permissions.remove(
            BusinessPermission.objects.get(code="contractual_records.view")
        )
        detail = self.client.get(
            reverse("contracts:detail", args=[self.contracts[0].pk])
        )
        url = reverse("contracts:commercial_review", args=[self.contracts[0].pk])
        self.assertNotContains(detail, f'href="{url}"')
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_other_project_and_tenant_remain_inaccessible(self):
        for contract in self.contracts[1:]:
            with self.subTest(contract=contract.pk):
                self.assertEqual(
                    self.client.get(
                        reverse("contracts:detail", args=[contract.pk])
                    ).status_code,
                    404,
                )
                self.assertEqual(
                    self.client.get(
                        reverse("contracts:commercial_review", args=[contract.pk])
                    ).status_code,
                    403,
                )
