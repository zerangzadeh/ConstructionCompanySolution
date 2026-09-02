from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
    get_organization_estimates,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.projects.models import ProjectPhaseStatus
from apps.projects.services import (
    create_project,
    create_project_phase,
    create_project_site,
)


class EstimateServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="estimate-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-estimate-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Estimate Company",
            slug="estimate-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Estimate Company",
            slug="other-estimate-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-ESTIMATE",
            name="Estimate project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="SITE-ESTIMATE",
            name="Estimate site",
        )
        self.phase = create_project_phase(
            organization=self.organization,
            site=self.site,
            actor=self.owner,
            code="PH-ESTIMATE",
            name="Estimate phase",
            status=ProjectPhaseStatus.PLANNING,
        )

    def test_create_estimate_and_add_decimal_items(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-001",
            title="Initial estimate",
        )
        item = add_estimate_item(
            estimate=estimate,
            actor=self.owner,
            description="Concrete",
            quantity=Decimal("12.5000"),
            unit_price=Decimal("80.25"),
            unit="m3",
        )

        estimate.refresh_from_db()
        self.assertEqual(item.line_total, Decimal("1003.13"))
        self.assertEqual(estimate.total_amount, Decimal("1003.13"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ESTIMATE_ITEM_ADDED,
                organization=self.organization,
            ).exists()
        )

    def test_estimate_number_is_unique_per_organization(self) -> None:
        create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-002",
            title="First",
        )
        with self.assertRaisesMessage(
            ValueError,
            "An estimate with this number already exists.",
        ):
            create_estimate(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                estimate_number="E-002",
                title="Duplicate",
            )

    def test_estimate_rejects_cross_tenant_project(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-EST",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            create_estimate(
                organization=self.organization,
                project=other_project,
                actor=self.owner,
                estimate_number="E-003",
                title="Invalid estimate",
            )

    def test_estimate_can_be_assigned_to_a_project_phase(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            phase=self.phase,
            actor=self.owner,
            estimate_number="E-PHASE-001",
            title="Phase estimate",
        )

        self.assertEqual(estimate.phase, self.phase)
        event = AuditEvent.objects.get(
            action=AuditAction.ESTIMATE_CREATED,
            entity_id=estimate.pk,
        )
        self.assertEqual(event.metadata["phase_id"], str(self.phase.pk))

    def test_estimate_rejects_phase_from_another_project(self) -> None:
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-ESTIMATE-OTHER",
            name="Other estimate project",
        )
        other_site = create_project_site(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            code="SITE-ESTIMATE-OTHER",
            name="Other estimate site",
        )
        other_phase = create_project_phase(
            organization=self.organization,
            site=other_site,
            actor=self.owner,
            code="PH-ESTIMATE-OTHER",
            name="Other estimate phase",
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "The project phase does not belong to this project.",
        ):
            create_estimate(
                organization=self.organization,
                project=self.project,
                phase=other_phase,
                actor=self.owner,
                estimate_number="E-PHASE-INVALID",
                title="Invalid phase estimate",
            )

    def test_estimate_rejects_invalid_item_values(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-004",
            title="Validation estimate",
        )

        with self.assertRaisesMessage(
            ValueError,
            "Item quantity must be positive.",
        ):
            add_estimate_item(
                estimate=estimate,
                actor=self.owner,
                description="Invalid",
                quantity=Decimal(0),
                unit_price=Decimal("10.00"),
            )

    def test_estimate_queryset_is_tenant_scoped(self) -> None:
        create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-005",
            title="Visible estimate",
        )

        estimates = get_organization_estimates(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(estimates.values_list("title", flat=True)),
            ["Visible estimate"],
        )
        with self.assertRaises(PermissionDenied):
            get_organization_estimates(
                user=self.other_user,
                organization=self.organization,
            )

    def test_approve_estimate_records_actor_and_locks_items(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-006",
            title="Approval estimate",
        )
        add_estimate_item(
            estimate=estimate,
            actor=self.owner,
            description="Labor",
            quantity=Decimal(2),
            unit_price=Decimal("50.00"),
        )

        approve_estimate(estimate=estimate, actor=self.owner)

        estimate.refresh_from_db()
        self.assertEqual(estimate.status, "approved")
        self.assertEqual(estimate.approved_by, self.owner)
        self.assertIsNotNone(estimate.approved_at)
        with self.assertRaisesMessage(
            ValueError,
            "Cannot modify an approved estimate.",
        ):
            add_estimate_item(
                estimate=estimate,
                actor=self.owner,
                description="Locked item",
                quantity=Decimal(1),
                unit_price=Decimal("1.00"),
            )

    def test_only_draft_estimates_can_be_approved(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-007",
            title="Approval estimate",
        )
        approve_estimate(estimate=estimate, actor=self.owner)

        with self.assertRaisesMessage(
            ValueError,
            "Only draft estimates can be approved.",
        ):
            approve_estimate(estimate=estimate, actor=self.owner)

    def test_manager_cannot_approve_estimate(self) -> None:
        manager = User.objects.create_user(
            username="estimate-manager",
            password="test-password",
        )
        self.organization.memberships.create(
            user=manager,
            role=MembershipRole.MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-008",
            title="Manager approval estimate",
        )

        with self.assertRaises(PermissionDenied):
            approve_estimate(estimate=estimate, actor=manager)

    def test_approve_view_changes_status(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-VIEW-APPROVE",
            title="View approval estimate",
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse(
                "estimates:approve",
                kwargs={"estimate_id": estimate.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "estimates:detail",
                kwargs={"estimate_id": estimate.pk},
            ),
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, "approved")

    def test_approve_view_rejects_manager(self) -> None:
        manager = User.objects.create_user(
            username="view-estimate-manager",
            password="test-password",
        )
        self.organization.memberships.create(
            user=manager,
            role=MembershipRole.MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-VIEW-MANAGER",
            title="Manager view estimate",
        )
        self.client.force_login(manager)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse(
                "estimates:approve",
                kwargs={"estimate_id": estimate.pk},
            )
        )

        self.assertEqual(response.status_code, 403)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, "draft")

    def test_estimate_list_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("estimates:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_estimate_create_view_limits_project_choices(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.other_organization.projects.create(
            code="P-HIDDEN",
            name="Hidden project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        response = self.client.get(reverse("estimates:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, "Hidden project")

    def test_estimate_detail_adds_item(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-VIEW-001",
            title="View estimate",
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("estimates:detail", kwargs={"estimate_id": estimate.pk}),
            {
                "description": "Steel",
                "quantity": "2.5",
                "unit": "ton",
                "unit_price": "100.00",
                "sort_order": "1",
            },
        )

        self.assertRedirects(
            response,
            reverse("estimates:detail", kwargs={"estimate_id": estimate.pk}),
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.total_amount, Decimal("250.00"))
