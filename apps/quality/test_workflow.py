from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project
from apps.quality.models import (
    QualityIssue,
    QualityIssueSeverity,
    QualityIssueStatus,
    QualityIssueType,
)
from apps.quality.services import (
    _assign_quality_issue_domain,
    _close_quality_issue_domain,
    _create_quality_issue_domain,
    _review_quality_issue_domain,
    _start_quality_corrective_action_domain,
    _submit_quality_issue_for_verification_domain,
    _verify_quality_issue_domain,
    assign_quality_issue,
    close_quality_issue,
    review_quality_issue,
    start_quality_corrective_action,
    submit_quality_issue_for_verification,
    verify_quality_issue,
)
from apps.quality.tests import QualityTestBase
from apps.quality.workflow import (
    COMPATIBILITY_CONFIGURATION,
    SUBJECT_TYPE,
    TEMPLATE_CODE,
    backfill_open_quality_issues,
    quality_shadow_comparison,
)
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTemplate,
    WorkItemStatus,
)
from apps.workflows.registry import registry
from apps.workflows.runtime import claim_work_item, complete_work_item


class QualityWorkflowTests(QualityTestBase):
    def _advance_to_assigned(self, issue: QualityIssue) -> None:
        review_quality_issue(
            organization=self.organization, actor=self.owner, issue_id=issue.pk
        )
        assign_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            due_date=timezone.localdate() + timedelta(days=2),
            responsible_user=self.owner,
        )

    def test_complete_cycle_uses_shared_workbench_and_domain_services(self) -> None:
        self.assertEqual(
            WorkflowTemplate.objects.get(code=TEMPLATE_CODE).configuration,
            COMPATIBILITY_CONFIGURATION,
        )
        issue = self.create_issue()
        instance = WorkflowInstance.objects.get(
            organization=self.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=issue.pk,
        )
        self.assertEqual(instance.work_items.get().action_key, "review")
        self._advance_to_assigned(issue)
        issue.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(
            instance.subject_context["responsible_display"], self.owner.username
        )
        item = instance.work_items.get(status=WorkItemStatus.OPEN)
        self.assertEqual(
            item.due_at.astimezone(
                ZoneInfo(self.organization.settings.timezone)
            ).date(),
            issue.due_date,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("workflows:workbench"))
        self.assertContains(response, "آغاز اقدام اصلاحی")
        self.assertContains(
            response, reverse("quality:detail", kwargs={"issue_id": issue.pk})
        )
        start_quality_corrective_action(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action="Repair defective concrete",
        )
        submit_quality_issue_for_verification(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action_result="Repair cured and documented",
        )
        verify_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            verification_summary="Inspection accepted",
        )
        close_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            closure_summary="Consultant acceptance recorded",
        )
        instance.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(issue.status, QualityIssueStatus.CLOSED)
        self.assertEqual(
            instance.work_items.filter(status=WorkItemStatus.COMPLETED).count(), 6
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_type="quality_issue",
                entity_id=str(issue.pk),
            ).count(),
            7,
        )

    def test_field_validation_permission_tenant_scope_and_candidacy_are_rechecked(
        self,
    ) -> None:
        issue = self.create_issue()
        with self.assertRaises(PermissionDenied):
            review_quality_issue(
                organization=self.other_organization,
                actor=self.other_owner,
                issue_id=issue.pk,
            )
        manager = User.objects.create_user(username="quality-manager")
        membership = self.organization.memberships.create(
            user=manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        item = WorkflowInstance.objects.get(subject_id=issue.pk).work_items.get()
        item.candidates.filter(membership=membership).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            review_quality_issue(
                organization=self.organization, actor=manager, issue_id=issue.pk
            )
        self._advance_to_assigned(issue)
        with self.assertRaises((ValueError, ValidationError)):
            start_quality_corrective_action(
                organization=self.organization,
                actor=self.owner,
                issue_id=issue.pk,
                corrective_action="  ",
            )
        self.assertEqual(
            QualityIssue.objects.get(pk=issue.pk).status,
            QualityIssueStatus.ASSIGNED,
        )

    def test_backfill_is_repeatable_preserves_final_history_and_shadows_legacy_candidates(
        self,
    ) -> None:
        issue = _create_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            issue_number="BACKFILL-OPEN",
            identified_at=timezone.now() - timedelta(minutes=1),
            issue_type=QualityIssueType.DEFECT,
            severity=QualityIssueSeverity.MAJOR,
            description="Open issue",
        )
        _review_quality_issue_domain(
            organization=self.organization, actor=self.owner, issue_id=issue.pk
        )
        _assign_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        issue.refresh_from_db()
        closed = _create_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            issue_number="BACKFILL-CLOSED",
            identified_at=timezone.now() - timedelta(minutes=1),
            issue_type=QualityIssueType.DEFECT,
            severity=QualityIssueSeverity.MAJOR,
            description="Closed issue",
        )
        _review_quality_issue_domain(
            organization=self.organization, actor=self.owner, issue_id=closed.pk
        )
        _assign_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=closed.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        _start_quality_corrective_action_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=closed.pk,
            corrective_action="Repair",
        )
        _submit_quality_issue_for_verification_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=closed.pk,
            corrective_action_result="Completed",
        )
        _verify_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=closed.pk,
            verification_summary="Accepted",
        )
        _close_quality_issue_domain(
            organization=self.organization,
            actor=self.owner,
            issue_id=closed.pk,
            closure_summary="Closed",
        )
        first = backfill_open_quality_issues(organization=self.organization)
        second = backfill_open_quality_issues(organization=self.organization)
        self.assertEqual((first.created, second.existing), (1, 1))
        instance = WorkflowInstance.objects.get(subject_id=issue.pk)
        self.assertEqual(instance.work_items.get().action_key, "start_action")
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=closed.pk).exists())
        self.assertFalse(
            quality_shadow_comparison(organization=self.organization, issue=issue)[
                "mismatch"
            ]
        )

    def test_retry_and_domain_failure_do_not_partially_complete_work(self) -> None:
        issue = self.create_issue()
        item = WorkflowInstance.objects.get(subject_id=issue.pk).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="quality-claim",
        )
        for _ in range(2):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="under_review",
                idempotency_key="quality-review",
                command_context={},
            )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.QUALITY_ISSUE_REVIEWED,
                entity_id=str(issue.pk),
            ).count(),
            1,
        )
        next_item = WorkflowInstance.objects.get(subject_id=issue.pk).work_items.get(
            status=WorkItemStatus.OPEN
        )
        command = registry.domain_commands["quality.quality_issue.assign"]
        try:
            registry.domain_commands[command.key] = replace(
                command,
                executor=lambda **kwargs: (_ for _ in ()).throw(
                    RuntimeError("failure")
                ),
            )
            with self.assertRaises(RuntimeError):
                assign_quality_issue(
                    organization=self.organization,
                    actor=self.owner,
                    issue_id=issue.pk,
                    due_date=timezone.localdate() + timedelta(days=1),
                    responsible_user=self.owner,
                )
        finally:
            registry.domain_commands[command.key] = command
        next_item.refresh_from_db()
        self.assertEqual(next_item.status, WorkItemStatus.OPEN)
        self.assertEqual(
            QualityIssue.objects.get(pk=issue.pk).status,
            QualityIssueStatus.UNDER_REVIEW,
        )


class QualityWorkflowConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def test_competing_reviews_commit_once(self) -> None:
        owner = User.objects.create_user(username="quality-race-owner")
        manager = User.objects.create_user(username="quality-race-manager")
        organization = Organization.objects.create(
            name="Quality Race", slug="quality-race"
        )
        OrganizationSettings.objects.create(organization=organization)
        for user, role in (
            (owner, MembershipRole.COMPANY_OWNER),
            (manager, MembershipRole.COMPANY_MANAGER),
        ):
            organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        project = Project.objects.create(
            organization=organization, code="RACE", name="Race"
        )
        issue = _create_quality_issue_domain(
            organization=organization,
            actor=owner,
            project=project,
            issue_number="RACE-1",
            identified_at=timezone.now() - timedelta(minutes=1),
            issue_type=QualityIssueType.DEFECT,
            severity=QualityIssueSeverity.MAJOR,
            description="Race",
        )
        from apps.quality.workflow import start_quality_workflow

        start_quality_workflow(organization=organization, issue=issue, actor=owner)
        barrier = Barrier(2)

        def review(user: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                review_quality_issue(
                    organization=organization, actor=user, issue_id=issue.pk
                )
                return "reviewed"
            except (ValueError, PermissionDenied, ValidationError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(review, (owner, manager)))
        self.assertEqual(outcomes.count("reviewed"), 1)
        self.assertEqual(
            QualityIssue.objects.get(pk=issue.pk).status,
            QualityIssueStatus.UNDER_REVIEW,
        )
