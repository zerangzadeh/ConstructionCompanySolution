from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import (
    DatabaseError,
    close_old_connections,
    connection,
    connections,
    models,
    transaction,
)
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.workforce.models import (
    Employee,
    EmployeePositionAssignment,
    Position,
    WorkTeam,
)

from .models import (
    WorkflowInstanceStatus,
    WorkflowStepInstanceStatus,
    WorkflowType,
    WorkItemAssignmentHistory,
    WorkItemStatus,
)
from .registry import SubjectSnapshot, registry
from .routing import resolve_step_candidates
from .runtime import (
    WorkflowConflict,
    cancel_workflow_instance,
    claim_work_item,
    complete_work_item,
    create_workflow_delegation,
    list_member_work_items,
    migrate_workflow_instance,
    reassign_work_item,
    release_work_item,
    resume_workflow_instance,
    revoke_workflow_delegation,
    start_workflow,
    suspend_workflow_instance,
)
from .services import (
    create_draft_version,
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
    supersede_workflow_version,
)

_COMMAND_STATE = {"fail": False, "calls": 0}


def _test_subject_loader(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    del actor
    if subject_id != organization.pk:
        raise PermissionDenied("موضوع تست متعلق به سازمان نیست.")
    queryset = (
        Organization.objects.select_for_update() if for_update else Organization.objects
    )
    try:
        subject = queryset.get(pk=subject_id)
    except Organization.DoesNotExist as exc:
        raise PermissionDenied("موضوع تست متعلق به سازمان نیست.") from exc
    owner = organization.memberships.filter(
        status=MembershipStatus.ACTIVE,
        role_definition__is_owner=True,
    ).first()
    return SubjectSnapshot(
        subject=subject,
        subject_id=str(subject.pk),
        organization_id=str(organization.pk),
        attributes={
            "amount": "100.00",
            "project_id": "project-1",
            "status": "submitted",
            "created_by_id": str(owner.user_id) if owner else "",
        },
        creator_membership_id=str(owner.pk) if owner else None,
        submitter_membership_id=str(owner.pk) if owner else None,
        display=subject.name,
    )


def _test_domain_command(*, subject: Organization, **kwargs: object) -> None:
    del kwargs
    _COMMAND_STATE["calls"] += 1
    Organization.objects.filter(pk=subject.pk).update(legal_name="runtime-command")
    if _COMMAND_STATE["fail"]:
        raise RuntimeError("domain command failed")


def _configuration(
    routes: list[dict[str, object]],
    *,
    step_permission: str = "",
    decision_configuration: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "steps": [
            {"key": "start", "step_type": "start", "is_start": True},
            {
                "key": "decision",
                "step_type": "approval",
                "required_permission": step_permission,
                "configuration": decision_configuration
                or {"decision_policy": "any", "due_hours": 24, "priority": 10},
                "routing": routes,
            },
            {"key": "approved", "step_type": "end", "is_terminal": True},
        ],
        "transitions": [
            {
                "source": "start",
                "target": "decision",
                "outcome": "submitted",
                "is_default": True,
            },
            {
                "source": "decision",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "procurement.purchase_request.approve",
                "required_permission": step_permission,
            },
        ],
    }


class RuntimeRegistryMixin:
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._adapter = registry.subject_adapters["procurement.purchase_request"]
        cls._approve = registry.domain_commands["procurement.purchase_request.approve"]
        registry.subject_adapters["procurement.purchase_request"] = replace(
            cls._adapter, loader=_test_subject_loader
        )
        registry.domain_commands["procurement.purchase_request.approve"] = replace(
            cls._approve, executor=_test_domain_command
        )

    @classmethod
    def tearDownClass(cls) -> None:
        registry.subject_adapters["procurement.purchase_request"] = cls._adapter
        registry.domain_commands["procurement.purchase_request.approve"] = cls._approve
        super().tearDownClass()


class RuntimeTestBase(RuntimeRegistryMixin):
    def setUp(self) -> None:
        _COMMAND_STATE.update(fail=False, calls=0)
        self.owner = User.objects.create_user(
            username=f"runtime-owner-{self._testMethodName}", password="password"
        )
        self.organization = create_organization_with_owner(
            name=f"Runtime {self._testMethodName}",
            slug=f"runtime-{self._testMethodName}",
            owner=self.owner,
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.workflow_type = WorkflowType.objects.get(
            code="procurement.purchase_request_approval"
        )

    def add_member(
        self, suffix: str, role: str = MembershipRole.MEMBER
    ) -> tuple[User, OrganizationMembership]:
        user = User.objects.create_user(
            username=f"runtime-{suffix}-{self._testMethodName}", password="password"
        )
        role_definition = OrganizationRole.objects.get(code=role)
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=role,
            role_definition=role_definition,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        return user, membership

    def add_position_holder(
        self,
        *,
        suffix: str,
        position: Position,
        user: User | None = None,
    ) -> tuple[User, OrganizationMembership, EmployeePositionAssignment]:
        if user is None:
            user, membership = self.add_member(suffix)
        else:
            membership = OrganizationMembership.objects.get(
                organization=self.organization, user=user
            )
        employee = Employee.objects.create(
            organization=self.organization,
            user=user,
            employee_number=f"EMP-{suffix}-{self._testMethodName}"[:50],
            first_name="Test",
            last_name=suffix,
        )
        assignment = EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            position=position,
            start_date=timezone.localdate() - timedelta(days=1),
        )
        return user, membership, assignment

    def create_version(
        self,
        routes: list[dict[str, object]] | None = None,
        *,
        publish: bool = True,
        step_permission: str = "",
        code: str = "runtime",
    ):
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=self.workflow_type.code,
            code=f"{code}-{self._testMethodName}"[:100],
            name="Runtime workflow",
            scope={"classification": code} if code != "runtime" else {},
        )
        version = edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=_configuration(
                routes
                or [{"resolver_type": "organization_owner", "configuration": {}}],
                step_permission=step_permission,
            ),
        )
        if publish:
            version = publish_workflow_version(
                actor=self.owner,
                organization=self.organization,
                version_id=version.pk,
            )
        return version

    def start(self, version, key: str = "start-1"):
        return start_workflow(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            subject_id=self.organization.pk,
            idempotency_key=f"{key}-{self._testMethodName}",
        )


class WorkflowRuntimeTests(RuntimeTestBase, TestCase):
    def test_only_published_versions_start_and_start_is_idempotent(self) -> None:
        draft = self.create_version(publish=False)
        with self.assertRaises(ValidationError):
            self.start(draft)
        published = publish_workflow_version(
            actor=self.owner,
            organization=self.organization,
            version_id=draft.pk,
        )
        first = self.start(published)
        second = self.start(published)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.work_items.count(), 1)

    def test_owner_fallback_operates_without_workforce(self) -> None:
        position = Position.objects.create(
            organization=self.organization,
            code="EMPTY",
            title="Empty",
        )
        version = self.create_version(
            [
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
        )
        instance = self.start(version)
        candidate = instance.work_items.get().candidates.get()
        self.assertEqual(candidate.membership, self.owner_membership)
        self.assertEqual(
            list(
                list_member_work_items(actor=self.owner, organization=self.organization)
            ),
            [instance.work_items.get()],
        )
        self.assertEqual(
            Employee.objects.filter(organization=self.organization).count(), 0
        )

    def test_membership_role_team_and_record_context_resolvers(self) -> None:
        user, membership = self.add_member("resolver")
        team = WorkTeam.objects.create(
            organization=self.organization, code="TEAM", name="Team"
        )
        employee = Employee.objects.create(
            organization=self.organization,
            user=user,
            work_team=team,
            employee_number=f"TEAM-{self._testMethodName}"[:50],
            first_name="Team",
            last_name="Member",
        )
        team.lead = employee
        team.save()
        fallback = {
            "resolver_type": "organization_owner",
            "configuration": {},
            "is_fallback": True,
        }
        route_sets = (
            (
                "explicit",
                {
                    "resolver_type": "explicit_membership",
                    "configuration": {"membership_id": str(membership.pk)},
                },
            ),
            (
                "role",
                {
                    "resolver_type": "organization_role",
                    "configuration": {"role_code": MembershipRole.MEMBER},
                },
            ),
            (
                "team-lead",
                {
                    "resolver_type": "work_team",
                    "configuration": {
                        "work_team_id": str(team.pk),
                        "mode": "lead",
                    },
                },
            ),
            (
                "team-members",
                {
                    "resolver_type": "work_team",
                    "configuration": {
                        "work_team_id": str(team.pk),
                        "mode": "members",
                    },
                },
            ),
        )
        for code, route in route_sets:
            item = self.start(
                self.create_version([route, fallback], code=code), key=code
            ).work_items.get()
            self.assertEqual(
                list(item.candidates.values_list("membership_id", flat=True)),
                [membership.pk],
            )
        record_item = self.start(
            self.create_version(
                [
                    {"resolver_type": "record_creator", "configuration": {}},
                    {"resolver_type": "record_submitter", "configuration": {}},
                    fallback,
                ],
                code="record",
            ),
            key="record",
        ).work_items.get()
        record_candidate = record_item.candidates.get()
        self.assertEqual(record_candidate.membership, self.owner_membership)
        self.assertEqual(len(record_candidate.routing_basis), 2)

    def test_position_single_multi_and_multi_position_deduplication(self) -> None:
        first = Position.objects.create(
            organization=self.organization, code="P1", title="Position 1"
        )
        second = Position.objects.create(
            organization=self.organization, code="P2", title="Position 2"
        )
        user, membership, _ = self.add_position_holder(suffix="holder", position=first)
        employee = Employee.objects.get(organization=self.organization, user=user)
        EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            position=second,
            start_date=timezone.localdate() - timedelta(days=1),
        )
        _, other_membership, _ = self.add_position_holder(
            suffix="other", position=first
        )
        version = self.create_version(
            [
                {
                    "resolver_type": "position",
                    "configuration": {"position_id": str(first.pk)},
                },
                {
                    "resolver_type": "position",
                    "configuration": {"position_id": str(second.pk)},
                },
                {
                    "resolver_type": "organization_owner",
                    "configuration": {},
                    "is_fallback": True,
                },
            ]
        )
        item = self.start(version).work_items.get()
        self.assertEqual(item.candidates.count(), 2)
        holder_candidate = item.candidates.get(membership=membership)
        self.assertEqual(len(holder_candidate.routing_basis), 2)
        self.assertTrue(item.candidates.filter(membership=other_membership).exists())

    def test_empty_routes_suspend_as_unresolvable(self) -> None:
        position = Position.objects.create(
            organization=self.organization, code="NONE", title="Nobody"
        )
        team = WorkTeam.objects.create(
            organization=self.organization, code="NONE", name="Nobody"
        )
        version = self.create_version(
            [
                {
                    "resolver_type": "position",
                    "configuration": {"position_id": str(position.pk)},
                },
                {
                    "resolver_type": "work_team",
                    "configuration": {
                        "work_team_id": str(team.pk),
                        "mode": "members",
                    },
                    "is_fallback": True,
                },
            ]
        )
        instance = self.start(version)
        self.assertEqual(instance.status, WorkflowInstanceStatus.SUSPENDED)
        self.assertEqual(instance.work_items.count(), 0)
        self.assertEqual(
            instance.step_instances.get(
                status=WorkflowStepInstanceStatus.ACTIVE
            ).step_definition.key,
            "decision",
        )

    def test_permission_and_candidacy_are_both_required(self) -> None:
        position = Position.objects.create(
            organization=self.organization, code="MEMBER", title="Member"
        )
        member_user, _, _ = self.add_position_holder(
            suffix="candidate", position=position
        )
        version = self.create_version(
            [
                {
                    "resolver_type": "position",
                    "configuration": {"position_id": str(position.pk)},
                },
                {
                    "resolver_type": "organization_owner",
                    "configuration": {},
                    "is_fallback": True,
                },
            ],
            step_permission="purchase_requests.approve",
        )
        item = self.start(version).work_items.get()
        claimed = claim_work_item(
            actor=member_user,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="candidate-claim",
        )
        self.assertEqual(claimed.status, WorkItemStatus.CLAIMED)
        with self.assertRaises(PermissionDenied):
            complete_work_item(
                actor=member_user,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="candidate-act",
            )
        release_work_item(
            actor=member_user,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="candidate-release",
        )
        with self.assertRaises(PermissionDenied):
            claim_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                idempotency_key="owner-not-candidate",
            )

    def test_effective_delegation_adds_only_current_delegate(self) -> None:
        _, delegate = self.add_member("delegate")
        _, future_delegate = self.add_member("future")
        now = timezone.now()
        active = create_workflow_delegation(
            actor=self.owner,
            organization=self.organization,
            delegator_membership_id=self.owner_membership.pk,
            delegate_membership_id=delegate.pk,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            reason="Coverage",
            idempotency_key="delegation-active",
        )
        create_workflow_delegation(
            actor=self.owner,
            organization=self.organization,
            delegator_membership_id=self.owner_membership.pk,
            delegate_membership_id=future_delegate.pk,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=2),
            reason="Future coverage",
            idempotency_key="delegation-future",
        )
        item = self.start(self.create_version()).work_items.get()
        ids = set(item.candidates.values_list("membership_id", flat=True))
        self.assertIn(delegate.pk, ids)
        self.assertNotIn(future_delegate.pk, ids)
        same = create_workflow_delegation(
            actor=self.owner,
            organization=self.organization,
            delegator_membership_id=self.owner_membership.pk,
            delegate_membership_id=delegate.pk,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            reason="Coverage",
            idempotency_key="delegation-active",
        )
        self.assertEqual(same.pk, active.pk)
        revoke_workflow_delegation(
            actor=self.owner,
            organization=self.organization,
            delegation_id=active.pk,
            reason="Returned",
        )
        item_after_revoke = self.start(
            self.create_version(code="after-revoke"), key="after-revoke"
        ).work_items.get()
        self.assertFalse(
            item_after_revoke.candidates.filter(membership=delegate).exists()
        )

    def test_claim_release_reassign_history_and_immutability(self) -> None:
        member_user, member = self.add_member("assignee")
        item = self.start(self.create_version()).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim",
        )
        release_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="release",
            reason="Queue again",
        )
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim-again",
        )
        item = reassign_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            assignee_membership_id=member.pk,
            reason="Handover",
            idempotency_key="reassign",
        )
        self.assertEqual(item.current_assignee, member)
        self.assertEqual(
            list(item.assignment_history.values_list("action", flat=True)),
            ["claim", "release", "claim", "reassign"],
        )
        history = item.assignment_history.first()
        history.reason = "mutated"
        with self.assertRaises(ValidationError):
            history.save()
        with self.assertRaises(ValidationError):
            WorkItemAssignmentHistory.objects.filter(pk=history.pk).update(reason="x")
        self.assertTrue(member_user.is_active)

    def test_domain_command_failure_rolls_back_all_runtime_changes(self) -> None:
        item = self.start(self.create_version()).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim",
        )
        _COMMAND_STATE["fail"] = True
        with self.assertRaises(RuntimeError):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="complete-fail",
            )
        item.refresh_from_db()
        self.organization.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.CLAIMED)
        self.assertNotEqual(self.organization.legal_name, "runtime-command")
        self.assertFalse(
            item.assignment_history.filter(idempotency_key="complete-fail").exists()
        )

    def test_complete_is_idempotent_and_advances_to_terminal(self) -> None:
        instance = self.start(self.create_version())
        item = instance.work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim",
        )
        first = complete_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            outcome="approved",
            idempotency_key="complete",
        )
        second = complete_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            outcome="approved",
            idempotency_key="complete",
        )
        instance.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(_COMMAND_STATE["calls"], 1)
        with self.assertRaises(ValidationError):
            first.save()
        candidate = first.candidates.get()
        candidate.routing_basis = []
        with self.assertRaises(ValidationError):
            candidate.save()
        terminal_step = instance.step_instances.order_by("-sequence").first()
        with self.assertRaises(ValidationError):
            terminal_step.save()
        with self.assertRaises(ValidationError):
            instance.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            models.QuerySet.update(
                type(first).objects.filter(pk=first.pk), status=WorkItemStatus.OPEN
            )

    def test_suspend_resume_cancel_are_idempotent_lifecycle_changes(self) -> None:
        instance = self.start(self.create_version())
        suspended = suspend_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            reason="Operational pause",
            idempotency_key="suspend",
        )
        self.assertEqual(suspended.status, WorkflowInstanceStatus.SUSPENDED)
        resumed = resume_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            reason="Continue",
            idempotency_key="resume",
        )
        self.assertEqual(resumed.status, WorkflowInstanceStatus.ACTIVE)
        cancelled = cancel_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            reason="No longer required",
            idempotency_key="cancel",
        )
        retried = cancel_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            reason="No longer required",
            idempotency_key="cancel",
        )
        self.assertEqual(cancelled.pk, retried.pk)
        self.assertEqual(cancelled.status, WorkflowInstanceStatus.CANCELLED)
        self.assertFalse(
            cancelled.work_items.filter(
                status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ).exists()
        )

    def test_open_instance_migration_maps_active_step_and_reconciles_items(
        self,
    ) -> None:
        first_version = self.create_version()
        instance = self.start(first_version)
        draft = create_draft_version(
            actor=self.owner,
            organization=self.organization,
            definition_id=first_version.definition_id,
            change_summary="Routing revision",
        )
        edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=draft.pk,
            configuration=_configuration(
                [{"resolver_type": "organization_owner", "configuration": {}}]
            ),
        )
        target = supersede_workflow_version(
            actor=self.owner,
            organization=self.organization,
            new_version_id=draft.pk,
            replaced_version_id=first_version.pk,
            reason="New routing",
        )
        migrated = migrate_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            target_version_id=target.pk,
            reason="Apply policy",
            idempotency_key="migrate-instance",
        )
        retried = migrate_workflow_instance(
            actor=self.owner,
            organization=self.organization,
            instance_id=instance.pk,
            target_version_id=target.pk,
            reason="Apply policy",
            idempotency_key="migrate-instance",
        )
        self.assertEqual(retried.version, target)
        self.assertEqual(migrated.version, target)
        self.assertEqual(
            migrated.step_instances.filter(status=WorkflowStepInstanceStatus.ACTIVE)
            .get()
            .step_definition.version,
            target,
        )
        self.assertEqual(
            migrated.work_items.filter(status=WorkItemStatus.CANCELLED).count(), 1
        )
        self.assertEqual(
            migrated.work_items.filter(status=WorkItemStatus.OPEN).count(), 1
        )

    def test_cross_tenant_rejection_and_routing_query_bound(self) -> None:
        version = self.create_version()
        other_owner = User.objects.create_user(
            username="runtime-other", password="password"
        )
        other = create_organization_with_owner(
            name="Other runtime", slug="other-runtime", owner=other_owner
        )
        with self.assertRaises(PermissionDenied):
            start_workflow(
                actor=self.owner,
                organization=self.organization,
                version_id=version.pk,
                subject_id=other.pk,
                idempotency_key="cross-subject",
            )
        instance = self.start(version)
        step = instance.step_instances.get(status=WorkflowStepInstanceStatus.ACTIVE)
        with CaptureQueriesContext(connection) as queries:
            result = resolve_step_candidates(
                instance=instance,
                step_id=step.step_definition_id,
                required_permission="",
            )
        self.assertEqual(len(result.candidates), 1)
        self.assertLessEqual(len(queries), 8)
        item = instance.work_items.get()
        with CaptureQueriesContext(connection) as claim_queries:
            claim_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                idempotency_key="query-count-claim",
            )
        self.assertLessEqual(len(claim_queries), 30)


class WorkflowRuntimeConcurrencyTests(RuntimeTestBase, TransactionTestCase):
    reset_sequences = True
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        # TransactionTestCase flushes migration-seeded role/permission rows. Restore
        # the serialized post-migration baseline for subsequently collected tests.
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def _run_in_thread(self, callback):
        close_old_connections()
        try:
            return callback()
        finally:
            close_old_connections()

    def test_concurrent_claim_and_decision_have_one_winner(self) -> None:
        item = self.start(self.create_version()).work_items.get()
        barrier = Barrier(2)

        def claim(key: str):
            barrier.wait()
            try:
                self._run_in_thread(
                    lambda: claim_work_item(
                        actor=User.objects.get(pk=self.owner.pk),
                        organization=Organization.objects.get(pk=self.organization.pk),
                        work_item_id=item.pk,
                        idempotency_key=key,
                    )
                )
                return "won"
            except WorkflowConflict:
                return "lost"

        with ThreadPoolExecutor(max_workers=2) as pool:
            claim_results = list(pool.map(claim, ("claim-a", "claim-b")))
        self.assertEqual(sorted(claim_results), ["lost", "won"])

        barrier = Barrier(2)

        def decide(key: str):
            barrier.wait()
            try:
                self._run_in_thread(
                    lambda: complete_work_item(
                        actor=User.objects.get(pk=self.owner.pk),
                        organization=Organization.objects.get(pk=self.organization.pk),
                        work_item_id=item.pk,
                        outcome="approved",
                        idempotency_key=key,
                    )
                )
                return "won"
            except WorkflowConflict:
                return "lost"

        with ThreadPoolExecutor(max_workers=2) as pool:
            decision_results = list(pool.map(decide, ("decide-a", "decide-b")))
        self.assertEqual(sorted(decision_results), ["lost", "won"])
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        self.assertEqual(item.assignment_history.filter(action="complete").count(), 1)
        self.assertEqual(_COMMAND_STATE["calls"], 1)
