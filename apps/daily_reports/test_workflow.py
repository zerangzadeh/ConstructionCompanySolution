from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.services import create_project, create_project_site
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTemplate,
    WorkItemStatus,
)
from apps.workflows.registry import registry
from apps.workflows.runtime import claim_work_item, complete_work_item

from .models import DailyReport, DailyReportStatus
from .services import (
    _approve_daily_report_domain,
    _submit_daily_report_domain,
    approve_daily_report,
    create_daily_report,
    submit_daily_report,
)
from .workflow import (
    COMPATIBILITY_CONFIGURATION,
    COMPATIBILITY_TEMPLATE_CODE,
    SUBJECT_TYPE,
    backfill_submitted_daily_reports,
    daily_report_shadow_comparison,
)


class DailyReportWorkflowFixture:
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="w51-owner")
        self.manager = User.objects.create_user(username="w51-manager")
        self.outsider = User.objects.create_user(username="w51-outsider")
        self.organization = Organization.objects.create(
            name="W51 Company", slug="w51-company"
        )
        self.other_organization = Organization.objects.create(
            name="W51 Other", slug="w51-other"
        )
        self.owner_membership = self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.manager_membership = self.organization.memberships.create(
            user=self.manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="W51-P",
            name="W51 project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="W51-S",
            name="W51 site",
        )

    def report(self, *, offset: int = 0) -> DailyReport:
        return create_daily_report(
            organization=self.organization,
            project=self.project,
            site=self.site,
            actor=self.owner,
            reporting_date=date(2026, 9, 16) + timedelta(days=offset),
            work_performed="Foundation work completed.",
        )


class DailyReportWorkflowTests(DailyReportWorkflowFixture, TestCase):
    def test_seeded_template_matches_code_owned_compatibility_policy(self) -> None:
        template = WorkflowTemplate.objects.get(code=COMPATIBILITY_TEMPLATE_CODE)
        self.assertEqual(template.configuration, COMPATIBILITY_CONFIGURATION)

    def test_manager_can_submit_another_authors_draft(self) -> None:
        report = self.report()
        submitted = submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.manager
        )
        self.assertEqual(submitted.status, DailyReportStatus.SUBMITTED)
        self.assertEqual(submitted.updated_by, self.manager)

    def test_submission_without_active_approver_remains_backfillable(self) -> None:
        member = User.objects.create_user(username="w51-member")
        self.organization.memberships.create(
            user=member, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE
        )
        report = create_daily_report(
            organization=self.organization,
            project=self.project,
            site=self.site,
            actor=member,
            reporting_date=date(2026, 9, 16),
            work_performed="Foundation work completed.",
        )
        self.organization.memberships.filter(
            pk__in=(self.owner_membership.pk, self.manager_membership.pk)
        ).update(status=MembershipStatus.SUSPENDED)
        submitted = submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=member
        )
        self.assertEqual(submitted.status, DailyReportStatus.SUBMITTED)
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=report.pk).exists())
        self.organization.memberships.filter(pk=self.manager_membership.pk).update(
            status=MembershipStatus.ACTIVE
        )
        result = backfill_submitted_daily_reports(organization=self.organization)
        self.assertEqual(result.created, 1)
        approved = approve_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.manager
        )
        self.assertEqual(approved.status, DailyReportStatus.APPROVED)

    def test_legacy_approval_uses_shared_work_item_and_workbench(self) -> None:
        report = self.report()
        submitted = submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        instance = WorkflowInstance.objects.get(
            organization=self.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=report.pk,
        )
        item = instance.work_items.get(status=WorkItemStatus.OPEN)
        self.assertEqual(submitted.status, DailyReportStatus.SUBMITTED)
        self.assertEqual(item.candidates.count(), 2)
        self.assertTrue(
            item.candidates.filter(membership=self.owner_membership).exists()
        )
        self.assertTrue(
            item.candidates.filter(membership=self.manager_membership).exists()
        )
        self.client.force_login(self.manager)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("workflows:workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("daily_reports:detail", kwargs={"report_id": report.pk})
        )
        approved = approve_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        instance.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(approved.status, DailyReportStatus.APPROVED)
        self.assertEqual(approved.approved_by, self.owner)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.WORK_ITEM_COMPLETED,
                entity_id=str(item.pk),
            ).exists()
        )

    def test_tenant_permission_and_candidate_are_independent(self) -> None:
        report = self.report()
        submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        with self.assertRaises(PermissionDenied):
            approve_daily_report(
                organization=self.other_organization,
                report_id=str(report.pk),
                actor=self.outsider,
            )
        item = WorkflowInstance.objects.get(subject_id=report.pk).work_items.get()
        item.candidates.filter(membership=self.manager_membership).update(
            is_active=False
        )
        with self.assertRaises(PermissionDenied):
            approve_daily_report(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.manager,
            )
        self.assertEqual(
            DailyReport.objects.get(pk=report.pk).status, DailyReportStatus.SUBMITTED
        )

    def test_backfill_is_repeatable_and_final_history_is_untouched(self) -> None:
        report = self.report()
        _submit_daily_report_domain(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        finalized = self.report(offset=1)
        _submit_daily_report_domain(
            organization=self.organization,
            report_id=str(finalized.pk),
            actor=self.owner,
        )
        _approve_daily_report_domain(
            organization=self.organization,
            report_id=str(finalized.pk),
            actor=self.owner,
        )
        first = backfill_submitted_daily_reports(organization=self.organization)
        second = backfill_submitted_daily_reports(organization=self.organization)
        self.assertEqual((first.created, first.existing), (1, 0))
        self.assertEqual((second.created, second.existing), (0, 1))
        self.assertFalse(
            WorkflowInstance.objects.filter(subject_id=finalized.pk).exists()
        )
        self.assertFalse(
            daily_report_shadow_comparison(
                organization=self.organization, report=report
            )["mismatch"]
        )
        item = WorkflowInstance.objects.get(subject_id=report.pk).work_items.get()
        item.candidates.filter(membership=self.owner_membership).update(is_active=False)
        self.assertTrue(
            daily_report_shadow_comparison(
                organization=self.organization, report=report
            )["mismatch"]
        )
        with self.assertRaises(PermissionDenied):
            daily_report_shadow_comparison(
                organization=self.other_organization, report=report
            )

    def test_legacy_open_report_can_be_approved_before_bulk_backfill(self) -> None:
        report = self.report()
        _submit_daily_report_domain(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        approved = approve_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.manager
        )
        self.assertEqual(approved.status, DailyReportStatus.APPROVED)
        instance = WorkflowInstance.objects.get(subject_id=report.pk)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)

    def test_failed_domain_command_rolls_back_claim_and_completion(self) -> None:
        report = self.report()
        submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        item = WorkflowInstance.objects.get(subject_id=report.pk).work_items.get()
        command = registry.domain_commands["daily_reports.daily_report.approve"]

        def fail(**kwargs: object) -> None:
            del kwargs
            raise RuntimeError("domain failure")

        registry.domain_commands[command.key] = replace(command, executor=fail)
        try:
            with self.assertRaises(RuntimeError):
                approve_daily_report(
                    organization=self.organization,
                    report_id=str(report.pk),
                    actor=self.owner,
                )
        finally:
            registry.domain_commands[command.key] = command
        report.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(report.status, DailyReportStatus.SUBMITTED)
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertFalse(item.assignment_history.filter(action="complete").exists())

    def test_failed_runtime_start_rolls_back_domain_submission(self) -> None:
        report = self.report()
        with (
            patch(
                "apps.daily_reports.workflow.start_workflow",
                side_effect=RuntimeError("runtime failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            submit_daily_report(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
            )
        report.refresh_from_db()
        self.assertEqual(report.status, DailyReportStatus.DRAFT)
        self.assertFalse(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(report.pk),
                action=AuditAction.DAILY_REPORT_SUBMITTED,
            ).exists()
        )

    def test_runtime_retry_does_not_duplicate_domain_approval(self) -> None:
        report = self.report()
        submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        item = WorkflowInstance.objects.get(subject_id=report.pk).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="w51-claim",
        )
        for _ in range(2):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="w51-approve",
            )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(report.pk),
                action=AuditAction.DAILY_REPORT_APPROVED,
            ).count(),
            1,
        )


class DailyReportConcurrencyTests(DailyReportWorkflowFixture, TransactionTestCase):
    serialized_rollback = True

    def test_competing_approvals_commit_only_once(self) -> None:
        report = self.report()
        submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        barrier = Barrier(2)

        def approve(user: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                approve_daily_report(
                    organization=self.organization,
                    report_id=str(report.pk),
                    actor=user,
                )
                return "approved"
            except (ValueError, PermissionDenied, ValidationError) as exc:
                return type(exc).__name__
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(approve, (self.owner, self.manager)))
        self.assertEqual(outcomes.count("approved"), 1)
        self.assertEqual(
            DailyReport.objects.get(pk=report.pk).status, DailyReportStatus.APPROVED
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(report.pk),
                action=AuditAction.DAILY_REPORT_APPROVED,
            ).count(),
            1,
        )
