from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.equipment.models import (
    Equipment,
    EquipmentStatus,
    MaintenanceRecord,
    MaintenanceStatus,
    MaintenanceType,
)
from apps.equipment.services import (
    _transition_maintenance_status_domain,
    create_maintenance_record,
    transition_maintenance_status,
)
from apps.equipment.tests import EquipmentTestBase
from apps.equipment.workflow import (
    SUBJECT_TYPE,
    TEMPLATE_CODE,
    WORKFLOW_TYPE_CODE,
    backfill_open_maintenance_workflows,
    maintenance_shadow_comparison,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTemplate,
    WorkflowType,
    WorkItemStatus,
)


class MaintenanceWorkflowTests(EquipmentTestBase, TestCase):
    def _scheduled(self, number: str = "W57-001"):
        return create_maintenance_record(
            organization=self.organization,
            actor=self.owner,
            equipment=self.make_equipment(number),
            record_number=number,
            maintenance_type=MaintenanceType.PREVENTIVE,
            summary="Scheduled service",
            scheduled_date=self.today + timedelta(days=2),
        )

    def test_cycle_uses_workbench_domain_service_due_date_and_terminal_history(
        self,
    ) -> None:
        record = self._scheduled()
        instance = WorkflowInstance.objects.get(
            organization=self.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=record.pk,
        )
        item = instance.work_items.get(status=WorkItemStatus.OPEN)
        self.assertEqual(item.action_key, "scheduled")
        self.assertEqual(
            item.due_at.astimezone(
                ZoneInfo(self.organization.settings.timezone)
            ).date(),
            record.scheduled_date,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("workflows:workbench"))
        self.assertContains(response, record.record_number)
        self.assertContains(
            response,
            reverse(
                "equipment:maintenance_status_change", kwargs={"record_id": record.pk}
            ),
        )
        transition_maintenance_status(
            organization=self.organization,
            actor=self.owner,
            record=record,
            target_status=MaintenanceStatus.IN_PROGRESS,
            effective_date=self.today,
        )
        record.refresh_from_db()
        record.equipment.refresh_from_db()
        self.assertEqual(record.status, MaintenanceStatus.IN_PROGRESS)
        self.assertEqual(record.equipment.status, EquipmentStatus.MAINTENANCE)
        self.assertEqual(
            instance.work_items.get(status=WorkItemStatus.OPEN).action_key,
            "in_progress",
        )
        transition_maintenance_status(
            organization=self.organization,
            actor=self.owner,
            record=record,
            target_status=MaintenanceStatus.COMPLETED,
            effective_date=self.today + timedelta(days=1),
            cost=Decimal("100.00"),
        )
        record.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(record.status, MaintenanceStatus.COMPLETED)
        self.assertEqual(record.cost, Decimal("100.00"))
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(
            instance.work_items.filter(status=WorkItemStatus.COMPLETED).count(), 2
        )
        self.assertEqual(
            transition_maintenance_status(
                organization=self.organization,
                actor=self.owner,
                record=record,
                target_status=MaintenanceStatus.COMPLETED,
                effective_date=self.today + timedelta(days=1),
                cost=Decimal("100.00"),
            ).pk,
            record.pk,
        )
        record.summary = "attempted edit"
        with self.assertRaises(ValidationError):
            record.save()

    def test_open_only_backfill_shadow_and_legacy_compatibility_path(self) -> None:
        open_record = MaintenanceRecord.objects.create(
            organization=self.organization,
            equipment=self.make_equipment("W57-BACKFILL"),
            record_number="W57-BACKFILL",
            maintenance_type=MaintenanceType.INSPECTION,
            summary="Existing open maintenance",
            scheduled_date=self.today,
        )
        completed = MaintenanceRecord.objects.create(
            organization=self.organization,
            equipment=self.make_equipment("W57-FINAL"),
            record_number="W57-FINAL",
            maintenance_type=MaintenanceType.INSPECTION,
            summary="Final maintenance",
            scheduled_date=self.today,
        )
        _transition_maintenance_status_domain(
            organization=self.organization,
            actor=self.owner,
            record=completed,
            target_status=MaintenanceStatus.COMPLETED,
            effective_date=self.today,
        )
        first = backfill_open_maintenance_workflows(organization=self.organization)
        second = backfill_open_maintenance_workflows(organization=self.organization)
        self.assertEqual((first.created, second.existing), (1, 1))
        self.assertFalse(
            WorkflowInstance.objects.filter(subject_id=completed.pk).exists()
        )
        self.assertFalse(
            maintenance_shadow_comparison(
                organization=self.organization, record=open_record
            )["mismatch"]
        )

    def test_cancellation_is_a_terminal_workbench_outcome(self) -> None:
        record = self._scheduled("W57-CANCEL")
        instance = WorkflowInstance.objects.get(subject_id=record.pk)
        transition_maintenance_status(
            organization=self.organization,
            actor=self.owner,
            record=record,
            target_status=MaintenanceStatus.CANCELLED,
            effective_date=self.today,
        )
        record.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(record.status, MaintenanceStatus.CANCELLED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertEqual(
            instance.work_items.get().completion_outcome, MaintenanceStatus.CANCELLED
        )
        record.notes = "attempted terminal change"
        with self.assertRaises(ValidationError):
            record.save()

    def test_tenant_scope_and_candidacy_are_rechecked(self) -> None:
        record = self._scheduled("W57-AUTH")
        item = WorkflowInstance.objects.get(subject_id=record.pk).work_items.get()
        item.candidates.filter(membership__user=self.owner).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            transition_maintenance_status(
                organization=self.organization,
                actor=self.owner,
                record=record,
                target_status=MaintenanceStatus.IN_PROGRESS,
                effective_date=self.today,
            )
        with self.assertRaises(PermissionDenied):
            transition_maintenance_status(
                organization=self.other_organization,
                actor=self.other_owner,
                record=record,
                target_status=MaintenanceStatus.IN_PROGRESS,
                effective_date=self.today,
            )

    def test_create_restores_missing_platform_catalog(self) -> None:
        WorkflowTemplate.objects.filter(code=TEMPLATE_CODE).delete()
        WorkflowType.objects.filter(code=WORKFLOW_TYPE_CODE).delete()

        record = self._scheduled("W57-CATALOG-RECOVERY")

        self.assertTrue(
            WorkflowType.objects.filter(
                code=WORKFLOW_TYPE_CODE, is_active=True
            ).exists()
        )
        self.assertTrue(
            WorkflowTemplate.objects.filter(
                workflow_type__code=WORKFLOW_TYPE_CODE,
                code=TEMPLATE_CODE,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            WorkflowInstance.objects.filter(
                organization=self.organization,
                subject_type=SUBJECT_TYPE,
                subject_id=record.pk,
            ).exists()
        )


class MaintenanceWorkflowConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        # TransactionTestCase flushes migration-seeded permission/catalog rows.
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def test_competing_start_actions_commit_once(self) -> None:
        owner = User.objects.create_user(username="w57-owner")
        manager = User.objects.create_user(username="w57-manager")
        organization = Organization.objects.create(name="W57", slug="w57")
        OrganizationSettings.objects.create(organization=organization)
        for user, role in (
            (owner, MembershipRole.COMPANY_OWNER),
            (manager, MembershipRole.COMPANY_MANAGER),
        ):
            organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        equipment = Equipment.objects.create(
            organization=organization,
            code="W57-EQ",
            name="W57 equipment",
            category="test",
        )
        record = create_maintenance_record(
            organization=organization,
            actor=owner,
            equipment=equipment,
            record_number="W57-RACE",
            maintenance_type=MaintenanceType.CORRECTIVE,
            summary="Race repair",
            scheduled_date=timezone.localdate(),
        )
        barrier = Barrier(2)

        def start(actor: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                transition_maintenance_status(
                    organization=Organization.objects.get(pk=organization.pk),
                    actor=User.objects.get(pk=actor.pk),
                    record=type(record).objects.get(pk=record.pk),
                    target_status=MaintenanceStatus.IN_PROGRESS,
                    effective_date=timezone.localdate(),
                )
                return "started"
            except (PermissionDenied, ValidationError, ValueError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, (owner, manager)))
        self.assertEqual(outcomes.count("started"), 1)
        self.assertEqual(
            type(record).objects.get(pk=record.pk).status, MaintenanceStatus.IN_PROGRESS
        )
