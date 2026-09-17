from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.estimates.models import Estimate, EstimateRevisionStatus, EstimateStatus
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
    create_estimate_revision,
)
from apps.estimates.workflow import (
    backfill_open_estimate_approvals,
    estimate_shadow_comparison,
    request_estimate_approval,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import set_active_organization
from apps.projects.services import create_project
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkItemStatus,
)
from apps.workflows.runtime import claim_work_item, complete_work_item


class EstimateWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="w54-estimate-owner")
        self.other_owner = User.objects.create_user(username="w54-estimate-other")
        self.organization = Organization.objects.create(
            name="W54 Estimate", slug="w54-estimate"
        )
        self.other_organization = Organization.objects.create(
            name="W54 Other", slug="w54-estimate-other"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="W54-E",
            name="Estimate workflow",
        )

    def _estimate(self, number: str = "W54-E-1"):
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number=number,
            title="Workflow estimate",
        )
        add_estimate_item(
            estimate=estimate,
            actor=self.owner,
            description="Concrete",
            quantity=Decimal(1),
            unit_price=Decimal(12),
        )
        return estimate

    def test_explicit_request_creates_workbench_item_and_preserves_revision_invariants(
        self,
    ) -> None:
        estimate = self._estimate()
        instance = request_estimate_approval(estimate=estimate, actor=self.owner)
        item = instance.work_items.get()
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertFalse(
            estimate_shadow_comparison(
                organization=self.organization, estimate=estimate
            )["mismatch"]
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()
        response = self.client.get(reverse("workflows:workbench"))
        self.assertContains(response, estimate.title)
        approved = approve_estimate(estimate=estimate, actor=self.owner)
        approved.refresh_from_db()
        self.assertEqual(approved.status, EstimateStatus.APPROVED)
        self.assertEqual(
            approved.current_revision.status, EstimateRevisionStatus.APPROVED
        )
        self.assertEqual(
            WorkflowInstance.objects.get(pk=instance.pk).status,
            WorkflowInstanceStatus.COMPLETED,
        )
        previous_revision = approved.current_revision
        revision = create_estimate_revision(estimate=approved, actor=self.owner)
        add_estimate_item(
            estimate=approved,
            actor=self.owner,
            description="Steel",
            quantity=Decimal(1),
            unit_price=Decimal(8),
        )
        request_estimate_approval(estimate=approved, actor=self.owner)
        approve_estimate(estimate=approved, actor=self.owner)
        revision.refresh_from_db()
        previous_revision.refresh_from_db()
        self.assertEqual(revision.status, EstimateRevisionStatus.APPROVED)
        self.assertEqual(previous_revision.status, EstimateRevisionStatus.SUPERSEDED)

    def test_drafts_are_never_backfilled_and_candidacy_and_tenant_scope_are_rechecked(
        self,
    ) -> None:
        estimate = self._estimate("W54-E-2")
        report = backfill_open_estimate_approvals(organization=self.organization)
        self.assertEqual((report.scanned, report.created), (0, 0))
        self.assertFalse(
            WorkflowInstance.objects.filter(subject_id=estimate.pk).exists()
        )
        instance = request_estimate_approval(estimate=estimate, actor=self.owner)
        item = instance.work_items.get()
        item.candidates.filter(membership__user=self.owner).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            approve_estimate(estimate=estimate, actor=self.owner)
        with self.assertRaises(PermissionDenied):
            request_estimate_approval(estimate=estimate, actor=self.other_owner)
        self.assertEqual(
            backfill_open_estimate_approvals(organization=self.organization).existing, 1
        )

    def test_work_item_retry_is_idempotent(self) -> None:
        estimate = self._estimate("W54-E-RETRY")
        item = request_estimate_approval(
            estimate=estimate, actor=self.owner
        ).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="w54-estimate-claim",
        )
        for _ in range(2):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="w54-estimate-approve",
            )
        self.assertEqual(
            Estimate.objects.get(pk=estimate.pk).status, EstimateStatus.APPROVED
        )


class EstimateWorkflowConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def test_competing_approvals_commit_once(self) -> None:
        owner = User.objects.create_user(username="w54-estimate-race-owner")
        manager = User.objects.create_user(username="w54-estimate-race-manager")
        organization = Organization.objects.create(
            name="W54 Estimate Race", slug="w54-estimate-race"
        )
        for user, role in (
            (owner, MembershipRole.COMPANY_OWNER),
            (manager, MembershipRole.COMPANY_MANAGER),
        ):
            organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        project = create_project(
            organization=organization, actor=owner, code="W54-RACE", name="Race"
        )
        estimate = create_estimate(
            organization=organization,
            project=project,
            actor=owner,
            estimate_number="W54-RACE-1",
            title="Race estimate",
        )
        add_estimate_item(
            estimate=estimate,
            actor=owner,
            description="Line",
            quantity=Decimal(1),
            unit_price=Decimal(1),
        )
        request_estimate_approval(estimate=estimate, actor=owner)
        barrier = Barrier(2)

        def approve(user: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                approve_estimate(
                    estimate=Estimate.objects.get(pk=estimate.pk), actor=user
                )
                return "approved"
            except (PermissionDenied, ValidationError, ValueError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(approve, (owner, manager)))
        self.assertEqual(outcomes.count("approved"), 1)
        self.assertEqual(
            Estimate.objects.get(pk=estimate.pk).status, EstimateStatus.APPROVED
        )
