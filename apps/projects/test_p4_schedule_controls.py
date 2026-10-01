from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects.models import (
    Project,
    ProjectControlItemKind,
    ProjectControlItemStatus,
    ProjectScheduleDependencyType,
    ProjectScheduleItem,
    ProjectScheduleRevision,
    ProjectScheduleStatus,
)
from apps.projects.services import (
    accept_project_schedule_baseline,
    accept_schedule_rebaseline,
    add_project_schedule_dependency,
    add_project_schedule_item,
    approve_project_change,
    create_project_schedule_revision,
    get_project_control_snapshot,
    propose_project_change,
    propose_schedule_rebaseline,
    record_project_control_item,
    transition_project_control_item,
)


class ProjectScheduleControlTests(TestCase):
    setUp = budget_helpers.BudgetPreparationTests.setUp

    def _schedule(self, occurrence: str = "SCHEDULE-1"):
        return create_project_schedule_revision(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id=occurrence,
            data_date=date(2026, 10, 1),
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 12, 31),
            calendar_reference="CALENDAR-EVIDENCE-1",
            assumptions="Draft dates only; no automated scheduling semantics.",
        )

    def test_permission_defaults_keep_acceptance_gates_closed(self) -> None:
        owner_role = OrganizationRole.objects.get(
            code=MembershipRole.COMPANY_OWNER, organization__isnull=True
        )
        permission_codes = set(
            owner_role.permissions.values_list("code", flat=True)
        )
        self.assertTrue(
            {
                str(BusinessPermissionCode.PROJECT_SCHEDULES_VIEW),
                str(BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_VIEW),
                str(BusinessPermissionCode.PROJECT_CHANGES_VIEW),
                str(BusinessPermissionCode.PROJECT_REBASELINES_VIEW),
            }.issubset(permission_codes)
        )
        self.assertTrue(
            {
                str(BusinessPermissionCode.PROJECT_SCHEDULE_BASELINES_ACCEPT),
                str(BusinessPermissionCode.PROJECT_CHANGES_APPROVE),
                str(BusinessPermissionCode.PROJECT_REBASELINES_ACCEPT),
            }.isdisjoint(permission_codes)
        )

    def test_schedule_milestones_dependency_integrity_and_idempotency(self) -> None:
        schedule = self._schedule()
        self.assertEqual(schedule.pk, self._schedule().pk)
        snapshot = get_project_control_snapshot(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        )
        self.assertEqual(snapshot.schedules, (schedule,))
        with self.assertRaises(PermissionDenied):
            get_project_control_snapshot(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
            )
        activity = add_project_schedule_item(
            schedule=schedule,
            actor=self.preparer,
            code="A-1",
            name="Foundation",
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 10, 10),
            source_reference="MANUAL-PLAN-1",
            wbs_node=self.wbs,
        )
        milestone = add_project_schedule_item(
            schedule=schedule,
            actor=self.preparer,
            code="M-1",
            name="Foundation complete",
            planned_start=date(2026, 10, 10),
            planned_finish=date(2026, 10, 10),
            source_reference="MANUAL-PLAN-1",
            is_milestone=True,
            wbs_node=self.wbs,
        )
        link = add_project_schedule_dependency(
            schedule=schedule,
            actor=self.preparer,
            predecessor_item=activity,
            successor_item=milestone,
            dependency_type=ProjectScheduleDependencyType.FINISH_START,
            lag_days=0,
            rationale="Reviewed planning dependency",
        )
        self.assertEqual(
            link.pk,
            add_project_schedule_dependency(
                schedule=schedule,
                actor=self.preparer,
                predecessor_item=activity,
                successor_item=milestone,
                dependency_type=ProjectScheduleDependencyType.FINISH_START,
                lag_days=0,
                rationale="Reviewed planning dependency",
            ).pk,
        )
        with self.assertRaisesMessage(ValueError, "cycle"):
            add_project_schedule_dependency(
                schedule=schedule,
                actor=self.preparer,
                predecessor_item=milestone,
                successor_item=activity,
                dependency_type=ProjectScheduleDependencyType.FINISH_START,
                lag_days=0,
                rationale="Invalid reverse dependency",
            )
        with self.assertRaises(ValidationError):
            add_project_schedule_item(
                schedule=schedule,
                actor=self.preparer,
                code="M-2",
                name="Invalid milestone",
                planned_start=date(2026, 10, 10),
                planned_finish=date(2026, 10, 11),
                source_reference="MANUAL-PLAN-1",
                is_milestone=True,
            )

    def test_tenant_scope_delay_evidence_and_status_serialization(self) -> None:
        schedule = self._schedule()
        item = add_project_schedule_item(
            schedule=schedule,
            actor=self.preparer,
            code="A-1",
            name="Foundation",
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 10, 10),
            source_reference="MANUAL-PLAN-1",
        )
        with self.assertRaises(PermissionDenied):
            record_project_control_item(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
                kind=ProjectControlItemKind.ISSUE,
                occurrence_id="CROSS-TENANT",
                title="Cross tenant",
                description="Must fail",
                identified_on=date(2026, 10, 1),
                owner_reference="OWNER",
                evidence_reference="EVIDENCE",
            )
        with self.assertRaisesMessage(ValidationError, "Delay observations"):
            record_project_control_item(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
                kind=ProjectControlItemKind.DELAY,
                occurrence_id="DELAY-BAD",
                title="Unsupported delay",
                description="Missing observed date",
                identified_on=date(2026, 10, 2),
                owner_reference="CONTROL-OWNER",
                evidence_reference="EVIDENCE",
            )
        delay = record_project_control_item(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            kind=ProjectControlItemKind.DELAY,
            occurrence_id="DELAY-1",
            title="Observed access delay",
            description="Contemporaneous planning observation",
            identified_on=date(2026, 10, 2),
            observed_from=date(2026, 10, 2),
            owner_reference="CONTROL-OWNER",
            evidence_reference="DAILY-REPORT-42",
            schedule_impact_description="Possible impact; not an EOT assessment.",
            schedule_item=item,
        )
        self.assertEqual(delay.responsibility_status, "undetermined")
        self.assertEqual(delay.contractual_impact_status, "unassessed")
        closed = transition_project_control_item(
            item=delay,
            actor=self.preparer,
            occurrence_id="DELAY-1-CLOSE",
            to_status=ProjectControlItemStatus.CLOSED,
            reason="Constraint observation ended; entitlement remains unassessed.",
        )
        self.assertEqual(
            closed.pk,
            transition_project_control_item(
                item=delay,
                actor=self.preparer,
                occurrence_id="DELAY-1-CLOSE",
                to_status=ProjectControlItemStatus.CLOSED,
                reason="Constraint observation ended; entitlement remains unassessed.",
            ).pk,
        )
        with self.assertRaisesMessage(ValueError, "Invalid control status"):
            transition_project_control_item(
                item=delay,
                actor=self.preparer,
                occurrence_id="STALE-SECOND-CLOSE",
                to_status=ProjectControlItemStatus.CLOSED,
                reason="Stale concurrent intent",
            )

    def test_snapshot_enforces_independent_read_permissions(self) -> None:
        schedule = self._schedule()
        register_item = record_project_control_item(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            kind=ProjectControlItemKind.ISSUE,
            occurrence_id="READ-SCOPE-ISSUE",
            title="Scoped issue",
            description="Must require the register read permission.",
            identified_on=date(2026, 10, 3),
            owner_reference="PROJECT-CONTROLS",
            evidence_reference="ISSUE-EVIDENCE",
        )
        change = propose_project_change(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="READ-SCOPE-CHANGE",
            title="Scoped change",
            reason="Read-scope test",
            evidence_reference="CHANGE-EVIDENCE",
            schedule_impact_description="Candidate only.",
        )
        reader = User.objects.create_user(username="schedule-only-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="schedule_only_reader",
            name="Schedule only reader",
        )
        role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_SCHEDULES_VIEW
            )
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=reader,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )

        snapshot = get_project_control_snapshot(
            organization=self.organization,
            project=self.project,
            actor=reader,
        )
        self.assertEqual(snapshot.schedules, (schedule,))
        self.assertEqual(snapshot.register_items, ())
        self.assertEqual(snapshot.change_proposals, ())
        self.assertEqual(snapshot.rebaseline_proposals, ())

        role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_VIEW
            ),
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_CHANGES_VIEW
            ),
        )
        snapshot = get_project_control_snapshot(
            organization=self.organization,
            project=self.project,
            actor=reader,
        )
        self.assertEqual(snapshot.register_items, (register_item,))
        self.assertEqual(snapshot.change_proposals, (change,))
        self.assertEqual(snapshot.rebaseline_proposals, ())

    def test_accepted_schedule_and_append_only_evidence_are_database_immutable(
        self,
    ) -> None:
        accepted = ProjectScheduleRevision.objects.create(
            organization=self.organization,
            project=self.project,
            version_number=1,
            occurrence_id="HISTORICAL-ACCEPTED-1",
            status=ProjectScheduleStatus.ACCEPTED,
            data_date=date(2026, 10, 1),
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 12, 31),
            calendar_reference="RETAINED-CALENDAR",
            assumptions="Retained accepted-history fixture",
            payload_hash="a" * 64,
            created_by=self.preparer,
            accepted_by=self.approver,
            accepted_at=timezone.now(),
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProjectScheduleRevision.objects.filter(pk=accepted.pk).update(
                assumptions="tampered"
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProjectScheduleItem.objects.bulk_create(
                [
                    ProjectScheduleItem(
                        organization=self.organization,
                        project=self.project,
                        schedule=accepted,
                        code="LATE",
                        name="Late payload",
                        planned_start=date(2026, 10, 1),
                        planned_finish=date(2026, 10, 2),
                        source_reference="BYPASS-ATTEMPT",
                    )
                ]
            )
        proposal = propose_project_change(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="CHANGE-1",
            title="Planning change observation",
            reason="Reviewed schedule evidence",
            evidence_reference="SITE-INSTRUCTION-REFERENCE-ONLY",
            schedule_impact_description="Candidate dates may move.",
            cost_impact_description="Not assessed; no financial mutation.",
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(proposal).objects.filter(pk=proposal.pk).update(title="tampered")

    def test_change_and_rebaseline_proposals_preserve_fail_closed_gates(self) -> None:
        accepted = ProjectScheduleRevision.objects.create(
            organization=self.organization,
            project=self.project,
            version_number=1,
            occurrence_id="HISTORICAL-BASELINE",
            status=ProjectScheduleStatus.ACCEPTED,
            data_date=date(2026, 10, 1),
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 12, 31),
            calendar_reference="RETAINED-CALENDAR",
            assumptions="Retained baseline",
            payload_hash="b" * 64,
            created_by=self.preparer,
            accepted_by=self.approver,
            accepted_at=timezone.now(),
        )
        candidate = create_project_schedule_revision(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="CANDIDATE-2",
            data_date=date(2026, 10, 15),
            planned_start=date(2026, 10, 1),
            planned_finish=date(2027, 1, 15),
            calendar_reference="CALENDAR-2",
            assumptions="Candidate only",
            predecessor=accepted,
        )
        change = propose_project_change(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="CHANGE-2",
            title="Candidate planning change",
            reason="Updated field evidence",
            evidence_reference="EVIDENCE-2",
            schedule_impact_description="Candidate finish 2027-01-15",
        )
        rebaseline = propose_schedule_rebaseline(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="REBASELINE-1",
            current_baseline=accepted,
            candidate_revision=candidate,
            change_proposal=change,
            reason="Comparison requested",
            evidence_reference="REVIEW-PACKET-1",
        )
        owner_role = OrganizationRole.objects.get(
            code=MembershipRole.COMPANY_OWNER, organization__isnull=True
        )
        owner_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_SCHEDULE_BASELINES_ACCEPT
            ),
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_CHANGES_APPROVE
            ),
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_REBASELINES_ACCEPT
            ),
        )
        with self.assertRaisesMessage(PermissionDenied, "not approved"):
            accept_project_schedule_baseline(schedule=candidate, actor=self.preparer)
        with self.assertRaisesMessage(PermissionDenied, "not approved"):
            approve_project_change(proposal=change, actor=self.preparer)
        with self.assertRaisesMessage(PermissionDenied, "not approved"):
            accept_schedule_rebaseline(proposal=rebaseline, actor=self.preparer)


class ProjectScheduleConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    setUp = budget_helpers.BudgetPreparationTests.setUp

    def test_concurrent_same_occurrence_creates_one_schedule_revision(self) -> None:
        barrier = Barrier(2)

        def create_once() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                revision = create_project_schedule_revision(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    project=Project.objects.get(pk=self.project.pk),
                    actor=User.objects.get(pk=self.preparer.pk),
                    occurrence_id="SCHEDULE-CONCURRENT-1",
                    data_date=date(2026, 10, 1),
                    planned_start=date(2026, 10, 1),
                    planned_finish=date(2026, 12, 31),
                    calendar_reference="CALENDAR-CONCURRENT",
                    assumptions="Same idempotent concurrent payload.",
                )
                return str(revision.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            revision_ids = list(pool.map(lambda _: create_once(), range(2)))

        self.assertEqual(revision_ids[0], revision_ids[1])
        self.assertEqual(
            ProjectScheduleRevision.objects.filter(
                project=self.project,
                occurrence_id="SCHEDULE-CONCURRENT-1",
            ).count(),
            1,
        )
