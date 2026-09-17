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
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project
from apps.safety.models import (
    SafetyIncident,
    SafetyIncidentSeverity,
    SafetyIncidentStatus,
    SafetyIncidentType,
)
from apps.safety.services import (
    _assign_safety_incident_domain,
    _close_safety_incident_domain,
    _create_safety_incident_domain,
    _resolve_safety_incident_domain,
    _review_safety_incident_domain,
    _start_corrective_action_domain,
    assign_safety_incident,
    close_safety_incident,
    create_safety_incident,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from apps.safety.tests import SafetyTestBase
from apps.safety.workflow import (
    COMPATIBILITY_CONFIGURATION,
    SUBJECT_TYPE,
    TEMPLATE_CODE,
    backfill_open_safety_incidents,
    safety_shadow_comparison,
)
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTemplate,
    WorkItemStatus,
)
from apps.workflows.registry import registry
from apps.workflows.runtime import claim_work_item, complete_work_item


class SafetyWorkflowTests(SafetyTestBase):
    def test_template_and_complete_cycle_keep_domain_authority(self) -> None:
        self.assertEqual(
            WorkflowTemplate.objects.get(code=TEMPLATE_CODE).configuration,
            COMPATIBILITY_CONFIGURATION,
        )
        incident = self.create_incident()
        instance = WorkflowInstance.objects.get(
            organization=self.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=incident.pk,
        )
        self.assertEqual(
            instance.work_items.get(status=WorkItemStatus.OPEN).action_key, "review"
        )
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            due_date=timezone.localdate() + timedelta(days=2),
            responsible_user=self.owner,
        )
        incident.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(
            instance.subject_context["responsible_display"], self.owner.username
        )
        active_item = instance.work_items.get(status=WorkItemStatus.OPEN)
        self.assertEqual(
            active_item.due_at.astimezone(ZoneInfo(self.organization.timezone)).date(),
            incident.due_date,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("workflows:workbench"))
        self.assertContains(response, "مسئول اقدام")
        self.assertContains(
            response, reverse("safety:detail", kwargs={"incident_id": incident.pk})
        )
        self.assertNotContains(
            response,
            reverse(
                "workflows:work_item_action",
                kwargs={
                    "work_item_id": instance.work_items.get(
                        status=WorkItemStatus.OPEN
                    ).pk
                },
            ),
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            corrective_action="Install guard",
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            resolution_summary="Guard installed",
        )
        close_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            closure_summary="Verified",
        )
        instance.refresh_from_db()
        incident.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(incident.status, SafetyIncidentStatus.CLOSED)
        self.assertEqual(
            instance.work_items.filter(status=WorkItemStatus.COMPLETED).count(), 5
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_type="safety_incident",
                entity_id=str(incident.pk),
            ).count(),
            6,
        )
        with self.assertRaises(ValidationError):
            incident.save()

    def test_required_input_and_direct_workbench_action_are_rejected(self) -> None:
        incident = self.create_incident()
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        item = WorkflowInstance.objects.get(subject_id=incident.pk).work_items.get(
            status=WorkItemStatus.OPEN
        )
        with self.assertRaises((ValueError, ValidationError)):
            assign_safety_incident(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                due_date=None,
                responsible_user=self.owner,
            )
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.UNDER_REVIEW,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.post(
            reverse("workflows:work_item_action", kwargs={"work_item_id": item.pk}),
            {"outcome": "assigned", "idempotency_key": "unsafe-direct"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.UNDER_REVIEW,
        )
        response = self.client.post(
            reverse("safety:assign", kwargs={"incident_id": incident.pk}), {}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.UNDER_REVIEW,
        )
        response = self.client.post(
            reverse("safety:assign", kwargs={"incident_id": incident.pk}),
            {
                "due_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "responsible_user": str(self.owner.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.ASSIGNED,
        )

    def test_each_text_input_is_required_before_completion(self) -> None:
        incident = self.create_incident()
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        with self.assertRaises((ValueError, ValidationError)):
            start_corrective_action(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                corrective_action="  ",
            )
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.ASSIGNED,
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            corrective_action="Install guard",
        )
        with self.assertRaises((ValueError, ValidationError)):
            resolve_safety_incident(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                resolution_summary="  ",
            )
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.ACTION_IN_PROGRESS,
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            resolution_summary="Guard installed",
        )
        with self.assertRaises((ValueError, ValidationError)):
            close_safety_incident(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
                closure_summary="  ",
            )
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.RESOLVED,
        )

    def test_tenant_permission_and_candidacy_are_independent(self) -> None:
        manager = User.objects.create_user(username="safety-manager")
        manager_membership = self.organization.memberships.create(
            user=manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        incident = self.create_incident()
        with self.assertRaises(PermissionDenied):
            review_safety_incident(
                organization=self.other_organization,
                actor=self.other_owner,
                incident_id=incident.pk,
            )
        item = WorkflowInstance.objects.get(subject_id=incident.pk).work_items.get()
        item.candidates.filter(membership=manager_membership).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            review_safety_incident(
                organization=self.organization, actor=manager, incident_id=incident.pk
            )
        with self.assertRaises(PermissionDenied):
            review_safety_incident(
                organization=self.organization,
                actor=self.viewer,
                incident_id=incident.pk,
            )
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.REPORTED,
        )

    def test_backfill_from_middle_state_is_repeatable_and_skips_closed(self) -> None:
        open_incident = _create_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            incident_number="BACKFILL-OPEN",
            occurred_at=timezone.now() - timedelta(minutes=1),
            incident_type=SafetyIncidentType.NEAR_MISS,
            severity=SafetyIncidentSeverity.HIGH,
            description="Open incident",
        )
        _review_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=open_incident.pk,
        )
        _assign_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=open_incident.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        open_incident.refresh_from_db()
        closed = _create_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            incident_number="BACKFILL-CLOSED",
            occurred_at=timezone.now() - timedelta(minutes=1),
            incident_type=SafetyIncidentType.NEAR_MISS,
            severity=SafetyIncidentSeverity.HIGH,
            description="Closed incident",
        )
        _review_safety_incident_domain(
            organization=self.organization, actor=self.owner, incident_id=closed.pk
        )
        _assign_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=closed.pk,
            due_date=timezone.localdate() + timedelta(days=1),
            responsible_user=self.owner,
        )
        _start_corrective_action_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=closed.pk,
            corrective_action="Fixed",
        )
        _resolve_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=closed.pk,
            resolution_summary="Resolved",
        )
        _close_safety_incident_domain(
            organization=self.organization,
            actor=self.owner,
            incident_id=closed.pk,
            closure_summary="Closed",
        )
        first = backfill_open_safety_incidents(organization=self.organization)
        second = backfill_open_safety_incidents(organization=self.organization)
        self.assertEqual((first.created, second.existing), (1, 1))
        instance = WorkflowInstance.objects.get(subject_id=open_incident.pk)
        active_item = instance.work_items.get()
        self.assertEqual(active_item.action_key, "start_action")
        self.assertEqual(
            active_item.due_at.astimezone(ZoneInfo(self.organization.timezone)).date(),
            open_incident.due_date,
        )
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=closed.pk).exists())
        self.assertFalse(
            safety_shadow_comparison(
                organization=self.organization, incident=open_incident
            )["mismatch"]
        )

    def test_runtime_retry_does_not_duplicate_review(self) -> None:
        incident = self.create_incident()
        item = WorkflowInstance.objects.get(subject_id=incident.pk).work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="safety-claim",
        )
        for _ in range(2):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="under_review",
                idempotency_key="safety-review",
                command_context={},
            )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.SAFETY_INCIDENT_REVIEWED,
                entity_id=str(incident.pk),
            ).count(),
            1,
        )

    def test_backfill_reconciles_candidates_added_after_work_item_creation(
        self,
    ) -> None:
        incident = self.create_incident()
        item = WorkflowInstance.objects.get(subject_id=incident.pk).work_items.get()
        original_candidates = item.candidates.filter(is_active=True).count()
        manager = User.objects.create_user(username="late-safety-manager")
        membership = self.organization.memberships.create(
            user=manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.assertTrue(
            safety_shadow_comparison(organization=self.organization, incident=incident)[
                "mismatch"
            ]
        )
        first = backfill_open_safety_incidents(organization=self.organization)
        second = backfill_open_safety_incidents(organization=self.organization)
        self.assertEqual((first.existing, second.existing), (1, 1))
        self.assertEqual(
            item.candidates.filter(is_active=True).count(), original_candidates + 1
        )
        self.assertTrue(
            item.candidates.filter(membership=membership, is_active=True).exists()
        )
        self.assertFalse(
            safety_shadow_comparison(organization=self.organization, incident=incident)[
                "mismatch"
            ]
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
                metadata__change="w5.2_backfill_reconcile",
            ).count(),
            1,
        )
        self.organization.memberships.filter(pk=membership.pk).update(
            status=MembershipStatus.SUSPENDED
        )
        backfill_open_safety_incidents(organization=self.organization)
        self.assertFalse(
            item.candidates.filter(membership=membership, is_active=True).exists()
        )
        self.assertFalse(
            safety_shadow_comparison(organization=self.organization, incident=incident)[
                "mismatch"
            ]
        )

    def test_domain_failure_rolls_back_claim_and_completion(self) -> None:
        incident = self.create_incident()
        item = WorkflowInstance.objects.get(subject_id=incident.pk).work_items.get()
        command = registry.domain_commands["safety.safety_incident.review"]
        try:
            registry.domain_commands[command.key] = replace(
                command,
                executor=lambda **kwargs: (_ for _ in ()).throw(
                    RuntimeError("domain failure")
                ),
            )
            with self.assertRaises(RuntimeError):
                review_safety_incident(
                    organization=self.organization,
                    actor=self.owner,
                    incident_id=incident.pk,
                )
        finally:
            registry.domain_commands[command.key] = command
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertFalse(item.assignment_history.filter(action="complete").exists())
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.REPORTED,
        )


class SafetyWorkflowConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def test_competing_reviews_commit_once(self) -> None:
        owner = User.objects.create_user(username="safety-race-owner")
        manager = User.objects.create_user(username="safety-race-manager")
        organization = Organization.objects.create(
            name="Safety Race", slug="safety-race"
        )
        organization.memberships.create(
            user=owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        organization.memberships.create(
            user=manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        project = Project.objects.create(
            organization=organization, code="RACE", name="Race"
        )
        incident = create_safety_incident(
            organization=organization,
            actor=owner,
            project=project,
            incident_number="RACE-1",
            occurred_at=timezone.now() - timedelta(minutes=1),
            incident_type=SafetyIncidentType.NEAR_MISS,
            severity=SafetyIncidentSeverity.HIGH,
            description="Race",
        )
        barrier = Barrier(2)

        def review(user: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                review_safety_incident(
                    organization=organization, actor=user, incident_id=incident.pk
                )
                return "reviewed"
            except (ValueError, PermissionDenied, ValidationError) as exc:
                return type(exc).__name__
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(review, (owner, manager)))
        self.assertEqual(outcomes.count("reviewed"), 1)
        self.assertEqual(
            SafetyIncident.objects.get(pk=incident.pk).status,
            SafetyIncidentStatus.UNDER_REVIEW,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=organization,
                action=AuditAction.SAFETY_INCIDENT_REVIEWED,
                entity_id=str(incident.pk),
            ).count(),
            1,
        )
