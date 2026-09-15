from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    OrganizationMembership,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowStepInstanceStatus,
    WorkItemStatus,
)
from apps.workflows.registry import registry
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)
from apps.workforce.models import Employee, EmployeePositionAssignment, Position

from .models import PurchaseRequest, PurchaseRequestStatus
from .services import (
    _submit_purchase_request_domain,
    add_purchase_request_item,
    approve_purchase_request,
    create_purchase_request,
    reject_purchase_request,
    submit_purchase_request,
)
from .tests import ProcurementFixtureMixin
from .workflow import (
    WORKFLOW_TYPE_CODE,
    backfill_submitted_purchase_requests,
    ensure_purchase_request_compatibility_workflow,
    purchase_request_shadow_comparison,
)


class PurchaseRequestWorkflowPilotTests(ProcurementFixtureMixin, TestCase):
    def _request(
        self,
        *,
        actor: User | None = None,
        project: Project | None = None,
        number: str = "W3-REQUEST",
    ) -> PurchaseRequest:
        actor = actor or self.owner
        request = create_purchase_request(
            organization=self.organization,
            actor=actor,
            project=project or self.project,
            request_number=number,
            title="W3 workflow request",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=actor,
            purchase_request=request,
            material=self.material,
            quantity=Decimal(1),
        )
        return request

    def _manager_with_position(
        self, *, username: str, position: Position
    ) -> tuple[User, OrganizationMembership]:
        user = User.objects.create_user(username=username)
        membership = self.organization.memberships.create(
            user=user,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        employee = Employee.objects.create(
            organization=self.organization,
            user=user,
            employee_number=f"EMP-{username}",
            first_name="Workflow",
            last_name=username,
        )
        EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            position=position,
            start_date=timezone.localdate() - timedelta(days=1),
        )
        return user, membership

    def test_compatibility_submit_and_self_approval_are_atomic(self) -> None:
        request = self._request()
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        instance = WorkflowInstance.objects.get(
            organization=self.organization, subject_id=request.pk
        )
        item = instance.work_items.get(status=WorkItemStatus.OPEN)
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        self.assertEqual(instance.work_items.count(), 1)
        owner_membership = self.organization.memberships.get(user=self.owner)
        self.assertTrue(item.candidates.filter(membership=owner_membership).exists())
        approved = approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        instance.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(approved.status, PurchaseRequestStatus.APPROVED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        retried = approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        self.assertEqual(retried.status, PurchaseRequestStatus.APPROVED)

    def test_reject_permission_candidacy_tenant_isolation_and_cancel(self) -> None:
        request = self._request(number="W3-REJECT")
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        with self.assertRaises(PermissionDenied):
            reject_purchase_request(
                organization=self.organization,
                actor=self.member,
                purchase_request=request,
                reason="not allowed",
            )
        with self.assertRaises(PermissionDenied):
            reject_purchase_request(
                organization=self.other_organization,
                actor=self.outsider,
                purchase_request=request,
                reason="cross tenant",
            )
        rejected = reject_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
            reason="rejected",
        )
        self.assertEqual(rejected.status, PurchaseRequestStatus.REJECTED)

        cancelled = self._request(number="W3-CANCEL")
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=cancelled,
        )
        from .services import cancel_purchase_request

        cancel_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=cancelled,
            reason="cancelled",
        )
        cancel_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=cancelled,
            reason="cancelled",
        )
        instance = WorkflowInstance.objects.get(subject_id=cancelled.pk)
        self.assertEqual(instance.status, WorkflowInstanceStatus.CANCELLED)
        self.assertFalse(
            instance.work_items.filter(
                status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ).exists()
        )

    def test_backfill_is_repeatable_skips_finalized_and_shadow_matches(self) -> None:
        request = self._request(number="W3-BACKFILL")
        _submit_purchase_request_domain(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        finalized = PurchaseRequest.objects.create(
            organization=self.organization,
            project=self.project,
            request_number="W3-FINAL",
            title="Already final",
            status=PurchaseRequestStatus.APPROVED,
            created_by=self.owner,
            updated_by=self.owner,
            approved_by=self.owner,
            approved_at=timezone.now(),
        )
        first = backfill_submitted_purchase_requests(organization=self.organization)
        second = backfill_submitted_purchase_requests(organization=self.organization)
        self.assertEqual((first.created, first.existing), (1, 0))
        self.assertEqual((second.created, second.existing), (0, 1))
        self.assertEqual(
            WorkflowInstance.objects.filter(subject_id=request.pk).count(), 1
        )
        self.assertFalse(
            WorkflowInstance.objects.filter(subject_id=finalized.pk).exists()
        )
        self.assertFalse(
            purchase_request_shadow_comparison(
                organization=self.organization, purchase_request=request
            )["mismatch"]
        )
        WorkflowInstance.objects.get(
            organization=self.organization,
            subject_id=request.pk,
        ).work_items.get().candidates.filter(membership__user=self.owner).update(
            is_active=False, removed_at=timezone.now()
        )
        self.assertTrue(
            purchase_request_shadow_comparison(
                organization=self.organization, purchase_request=request
            )["mismatch"]
        )

    def test_domain_command_failure_rolls_back_claim_and_decision(self) -> None:
        request = self._request(number="W3-ROLLBACK")
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        item = WorkflowInstance.objects.get(subject_id=request.pk).work_items.get()
        command = registry.domain_commands["procurement.purchase_request.approve"]

        def fail(**kwargs: object) -> None:
            del kwargs
            raise RuntimeError("domain failure")

        registry.domain_commands[command.key] = replace(command, executor=fail)
        try:
            with self.assertRaises(RuntimeError):
                approve_purchase_request(
                    organization=self.organization,
                    actor=self.owner,
                    purchase_request=request,
                )
        finally:
            registry.domain_commands[command.key] = command
        request.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(request.status, PurchaseRequestStatus.SUBMITTED)
        self.assertEqual(item.status, WorkItemStatus.OPEN)

    def test_project_policy_uses_position_multistage_and_strict_self_approval(
        self,
    ) -> None:
        ensure_purchase_request_compatibility_workflow(
            organization=self.organization, actor=self.owner
        )
        position = Position.objects.create(
            organization=self.organization, code="W3-APPROVER", title="W3 Approver"
        )
        submitter, _ = self._manager_with_position(
            username="w3-submitter", position=position
        )
        approver, _ = self._manager_with_position(
            username="w3-approver", position=position
        )
        route = [
            {
                "resolver_type": "position",
                "configuration": {"position_id": str(position.pk)},
            },
            {
                "resolver_type": "organization_owner",
                "configuration": {},
                "is_fallback": True,
            },
        ]
        decision = {
            "step_type": "approval",
            "configuration": {
                "decision_policy": "any",
                "exclude_submitter": True,
            },
            "routing": route,
        }
        configuration = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {"key": "first", **decision},
                {"key": "second", **decision},
                {"key": "approved", "step_type": "end", "is_terminal": True},
                {"key": "rejected", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "first",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {"source": "first", "target": "second", "outcome": "approved"},
                {
                    "source": "first",
                    "target": "rejected",
                    "outcome": "rejected",
                    "domain_command": "procurement.purchase_request.reject",
                    "required_permission": "purchase_requests.reject",
                },
                {
                    "source": "second",
                    "target": "approved",
                    "outcome": "approved",
                    "domain_command": "procurement.purchase_request.approve",
                    "required_permission": "purchase_requests.approve",
                },
                {
                    "source": "second",
                    "target": "rejected",
                    "outcome": "rejected",
                    "domain_command": "procurement.purchase_request.reject",
                    "required_permission": "purchase_requests.reject",
                },
            ],
        }
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=WORKFLOW_TYPE_CODE,
            code="w3-project-policy",
            name="W3 project policy",
            scope={"project_id": str(self.project.pk)},
        )
        version = edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=configuration,
        )
        publish_workflow_version(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
        )
        request = self._request(actor=submitter, number="W3-STRICT")
        submit_purchase_request(
            organization=self.organization,
            actor=submitter,
            purchase_request=request,
        )
        with self.assertRaises(PermissionDenied):
            approve_purchase_request(
                organization=self.organization,
                actor=submitter,
                purchase_request=request,
            )
        approve_purchase_request(
            organization=self.organization,
            actor=approver,
            purchase_request=request,
        )
        request.refresh_from_db()
        self.assertEqual(request.status, PurchaseRequestStatus.SUBMITTED)
        instance = WorkflowInstance.objects.get(subject_id=request.pk)
        self.assertTrue(
            instance.step_instances.filter(
                status=WorkflowStepInstanceStatus.ACTIVE,
                step_definition__key="second",
            ).exists()
        )
        approve_purchase_request(
            organization=self.organization,
            actor=approver,
            purchase_request=request,
        )
        request.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(request.status, PurchaseRequestStatus.APPROVED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)

    def test_amount_condition_is_rejected_without_canonical_request_amount(
        self,
    ) -> None:
        configuration = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "decision",
                    "step_type": "approval",
                    "configuration": {"decision_policy": "any"},
                    "routing": [
                        {
                            "resolver_type": "organization_owner",
                            "configuration": {},
                        }
                    ],
                },
                {"key": "approved", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "decision",
                    "outcome": "submitted",
                    "conditions": [
                        {
                            "condition_type": "amount_threshold",
                            "configuration": {"operator": "gte", "amount": "100"},
                        }
                    ],
                },
                {
                    "source": "decision",
                    "target": "approved",
                    "outcome": "approved",
                    "domain_command": "procurement.purchase_request.approve",
                    "required_permission": "purchase_requests.approve",
                },
            ],
        }
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=WORKFLOW_TYPE_CODE,
            code="invalid-amount-policy",
            name="Invalid amount policy",
            scope={"project_id": str(self.project.pk)},
        )
        version = edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=configuration,
        )
        with self.assertRaises(ValidationError):
            publish_workflow_version(
                actor=self.owner,
                organization=self.organization,
                version_id=version.pk,
            )


class PurchaseRequestWorkflowProvisioningTests(TestCase):
    def test_new_organization_receives_published_compatibility_workflow(self) -> None:
        owner = User.objects.create_user(username="w3-new-organization-owner")
        with self.captureOnCommitCallbacks(execute=True):
            organization = create_organization_with_owner(
                owner=owner,
                name="W3 New Organization",
                slug="w3-new-organization",
            )
        definition = WorkflowDefinition.objects.get(
            organization=organization,
            workflow_type__code=WORKFLOW_TYPE_CODE,
            scope={},
        )
        self.assertTrue(definition.versions.filter(status="published").exists())
