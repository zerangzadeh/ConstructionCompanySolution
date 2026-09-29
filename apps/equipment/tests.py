from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.equipment.models import (
    Equipment,
    EquipmentAssignment,
    EquipmentAssignmentStatus,
    EquipmentStatus,
    MaintenanceRecord,
    MaintenanceStatus,
    MaintenanceType,
)
from apps.equipment.services import (
    assign_equipment,
    create_equipment,
    create_maintenance_record,
    get_organization_equipment,
    get_organization_equipment_assignments,
    transition_equipment_assignment_status,
    transition_maintenance_status,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project, ProjectSite


class EquipmentTestBase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="equipment-owner")
        self.viewer = User.objects.create_user(username="equipment-viewer")
        self.other_owner = User.objects.create_user(username="other-equipment-owner")
        self.organization = Organization.objects.create(
            name="Equipment Co", slug="equipment-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Equipment Co", slug="other-equipment-co"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, timezone="Asia/Tehran"
        )
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="EQ-PROJ",
            name="Equipment Project",
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="MAIN",
            name="Main Site",
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Other Project",
        )
        self.today = timezone.localdate()

    def make_equipment(self, code: str = "EXC-001") -> Equipment:
        return Equipment.objects.create(
            organization=self.organization,
            code=code,
            name="بیل مکانیکی",
            category="ماشین‌آلات سنگین",
        )


class EquipmentModelTests(EquipmentTestBase):
    def test_equipment_is_tenant_owned_without_current_project_field(self) -> None:
        equipment = self.make_equipment("exc-001")

        self.assertEqual(equipment.code, "EXC-001")
        self.assertEqual(equipment.organization, self.organization)
        self.assertFalse(hasattr(equipment, "current_project"))

    def test_assignment_rejects_cross_tenant_project_and_site(self) -> None:
        equipment = self.make_equipment()

        with self.assertRaises(ValidationError):
            EquipmentAssignment.objects.create(
                organization=self.organization,
                equipment=equipment,
                project=self.other_project,
                start_date=self.today,
                status=EquipmentAssignmentStatus.ACTIVE,
            )

    def test_non_cancelled_assignment_ranges_cannot_overlap(self) -> None:
        equipment = self.make_equipment()
        EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=equipment,
            project=self.project,
            start_date=self.today,
            end_date=self.today + timedelta(days=5),
            status=EquipmentAssignmentStatus.ACTIVE,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            EquipmentAssignment.objects.create(
                organization=self.organization,
                equipment=equipment,
                project=self.project,
                start_date=self.today + timedelta(days=5),
                end_date=self.today + timedelta(days=10),
                status=EquipmentAssignmentStatus.SCHEDULED,
            )

        cancelled = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=equipment,
            project=self.project,
            start_date=self.today + timedelta(days=2),
            end_date=self.today + timedelta(days=3),
            status=EquipmentAssignmentStatus.CANCELLED,
        )
        self.assertEqual(cancelled.status, EquipmentAssignmentStatus.CANCELLED)

    def test_completed_maintenance_history_is_immutable_and_not_deletable(self) -> None:
        equipment = self.make_equipment()
        record = MaintenanceRecord.objects.create(
            organization=self.organization,
            equipment=equipment,
            record_number="MNT-001",
            maintenance_type=MaintenanceType.PREVENTIVE,
            status=MaintenanceStatus.COMPLETED,
            summary="سرویس دوره‌ای",
            scheduled_date=self.today,
            started_date=self.today,
            completed_date=self.today,
            cost=Decimal("1200.00"),
        )

        record.summary = "عنوان تغییریافته"
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()


class EquipmentServiceTests(EquipmentTestBase):
    def test_create_and_scoped_read_enforce_rbac_and_audit(self) -> None:
        equipment = create_equipment(
            organization=self.organization,
            actor=self.owner,
            code="crn-001",
            name="جرثقیل",
            category="بالابری",
        )

        self.assertEqual(
            list(
                get_organization_equipment(
                    user=self.viewer, organization=self.organization
                )
            ),
            [equipment],
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.EQUIPMENT_CREATED,
                entity_id=str(equipment.pk),
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            create_equipment(
                organization=self.organization,
                actor=self.viewer,
                code="DENIED",
                name="غلتک",
                category="راه‌سازی",
            )

    def test_assignment_lifecycle_preserves_history_and_derived_status(self) -> None:
        equipment = self.make_equipment()
        assignment = assign_equipment(
            organization=self.organization,
            actor=self.owner,
            equipment=equipment,
            project=self.project,
            site=self.site,
            start_date=self.today,
            purpose="عملیات خاکی",
        )
        equipment.refresh_from_db()

        self.assertEqual(assignment.status, EquipmentAssignmentStatus.ACTIVE)
        self.assertEqual(equipment.status, EquipmentStatus.ASSIGNED)
        self.assertEqual(
            get_organization_equipment_assignments(
                user=self.viewer,
                organization=self.organization,
                equipment=equipment,
            ).get(),
            assignment,
        )

        transition_equipment_assignment_status(
            organization=self.organization,
            actor=self.owner,
            assignment=assignment,
            target_status=EquipmentAssignmentStatus.COMPLETED,
            effective_date=self.today + timedelta(days=1),
        )
        equipment.refresh_from_db()
        assignment.refresh_from_db()

        self.assertEqual(assignment.status, EquipmentAssignmentStatus.COMPLETED)
        self.assertEqual(assignment.end_date, self.today + timedelta(days=1))
        self.assertEqual(equipment.status, EquipmentStatus.AVAILABLE)
        self.assertTrue(EquipmentAssignment.objects.filter(pk=assignment.pk).exists())

    def test_assignment_service_rejects_cross_tenant_and_overlap(self) -> None:
        equipment = self.make_equipment()
        assign_equipment(
            organization=self.organization,
            actor=self.owner,
            equipment=equipment,
            project=self.project,
            start_date=self.today,
            end_date=self.today + timedelta(days=7),
        )

        with self.assertRaises(ValueError):
            assign_equipment(
                organization=self.organization,
                actor=self.owner,
                equipment=equipment,
                project=self.project,
                start_date=self.today + timedelta(days=1),
                end_date=self.today + timedelta(days=2),
            )
        with self.assertRaises(PermissionDenied):
            assign_equipment(
                organization=self.organization,
                actor=self.owner,
                equipment=equipment,
                project=self.other_project,
                start_date=self.today + timedelta(days=10),
            )

    def test_maintenance_lifecycle_updates_equipment_and_audits(self) -> None:
        equipment = self.make_equipment()
        record = create_maintenance_record(
            organization=self.organization,
            actor=self.owner,
            equipment=equipment,
            record_number="mnt-100",
            maintenance_type=MaintenanceType.CORRECTIVE,
            summary="تعمیر سیستم هیدرولیک",
            scheduled_date=self.today,
        )
        transition_maintenance_status(
            organization=self.organization,
            actor=self.owner,
            record=record,
            target_status=MaintenanceStatus.IN_PROGRESS,
            effective_date=self.today,
        )
        equipment.refresh_from_db()
        self.assertEqual(equipment.status, EquipmentStatus.MAINTENANCE)

        transition_maintenance_status(
            organization=self.organization,
            actor=self.owner,
            record=record,
            target_status=MaintenanceStatus.COMPLETED,
            effective_date=self.today + timedelta(days=1),
            cost=Decimal("2500000.00"),
        )
        equipment.refresh_from_db()
        record.refresh_from_db()

        self.assertEqual(equipment.status, EquipmentStatus.AVAILABLE)
        self.assertEqual(record.status, MaintenanceStatus.COMPLETED)
        self.assertEqual(record.cost, Decimal("2500000.00"))
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(record.pk),
            ).count(),
            3,
        )


class EquipmentAdminTests(EquipmentTestBase):
    def test_equipment_admins_are_read_only(self) -> None:
        request = RequestFactory().get("/admin/")
        request.user = self.owner

        for model in (Equipment, EquipmentAssignment, MaintenanceRecord):
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))


class EquipmentPanelTests(EquipmentTestBase):
    def test_owner_can_open_scoped_equipment_pages(self) -> None:
        equipment = self.make_equipment()
        foreign_equipment = Equipment.objects.create(
            organization=self.other_organization,
            code="OTHER-EQ",
            name="Other equipment",
            category="Other",
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        self.assertEqual(self.client.get(reverse("equipment:list")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("equipment:detail", kwargs={"equipment_id": equipment.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "equipment:detail", kwargs={"equipment_id": foreign_equipment.pk}
                )
            ).status_code,
            404,
        )
