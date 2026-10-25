from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.organizations.models import MembershipScopeGrant
from apps.procurement.models import PurchaseRequest, PurchaseRequestStatus
from apps.procurement.services import (
    add_purchase_request_item,
    create_purchase_request,
    submit_purchase_request,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.procurement.workflow import load_purchase_request_subject
from apps.projects.models import Project
from apps.workflows.models import WorkflowInstance


class PurchaseRequestProjectScopeTests(ProcurementFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        membership = self.organization.memberships.get(user=self.owner)
        membership.scope_grants.update(revoked_at=timezone.now())
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=self.project,
            reason="Explicit scoped workflow test",
        )
        self.request = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            request_number="CEP079-SCOPED",
            title="Scoped requester",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.owner,
            purchase_request=self.request,
            material=self.material,
            quantity=Decimal(1),
        )

    def test_project_scoped_requester_can_submit_with_atomic_workflow(self):
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=self.request,
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, PurchaseRequestStatus.SUBMITTED)
        self.assertEqual(
            WorkflowInstance.objects.filter(subject_id=self.request.pk).count(), 1
        )

    def test_subject_loader_denies_other_project_and_foreign_tenant(self):
        ungranted = Project.objects.create(
            organization=self.organization,
            code="OTHER-SCOPE",
            name="Ungranted",
        )
        for project, organization in (
            (ungranted, self.organization),
            (self.other_project, self.other_organization),
        ):
            request = PurchaseRequest.objects.create(
                organization=organization,
                project=project,
                request_number="DENIED",
                title="Denied",
                created_by=self.owner,
            )
            with self.subTest(project=project.pk), self.assertRaises(PermissionDenied):
                load_purchase_request_subject(
                    organization=self.organization,
                    actor=self.owner,
                    subject_id=request.pk,
                    for_update=False,
                )
            self.assertFalse(
                WorkflowInstance.objects.filter(subject_id=request.pk).exists()
            )

    def test_subject_loader_denies_missing_permission_and_inactive_membership(self):
        self.organization.memberships.get(user=self.member).role_assignments.update(
            revoked_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            load_purchase_request_subject(
                organization=self.organization,
                actor=self.member,
                subject_id=self.request.pk,
                for_update=False,
            )
        self.organization.memberships.filter(user=self.owner).update(status="suspended")
        with self.assertRaises(PermissionDenied):
            load_purchase_request_subject(
                organization=self.organization,
                actor=self.owner,
                subject_id=self.request.pk,
                for_update=False,
            )
