from copy import deepcopy
from datetime import time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.documents import test_cep011 as baseline
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.services import create_project
from apps.workforce.models import Employee
from apps.workforce.person_services import end_work_relationship

from . import roster_services as service
from .models import AttendanceRecord, RosterSlot, RosterVersion, ShiftDefinition
from .services import create_shift, create_work_calendar


class RosterTests(TestCase):
    _relationship = baseline.EmployeeDocumentAccessTests._relationship

    def setUp(self):
        baseline.EmployeeDocumentAccessTests.setUp(self)
        self.member = OrganizationMembership.objects.get(
            user=self.owner, organization=self.organization
        )
        self.member.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[P.ROSTERS_MANAGE, P.ROSTERS_VIEW, P.TIME_CALENDARS_MANAGE]
            )
        )
        self.calendar = create_work_calendar(
            actor=self.owner,
            organization=self.organization,
            code="R22",
            name="تقویم برنامه",
            effective_from=self.today - timedelta(days=60),
            working_weekdays=[1, 2, 3, 4, 5],
        )
        self.day = create_shift(
            actor=self.owner,
            organization=self.organization,
            calendar=self.calendar,
            code="DAY",
            name="روز",
            starts_at=time(8),
            ends_at=time(16),
            crosses_midnight=False,
            effective_from=self.today - timedelta(days=60),
            breaks=[],
        )
        self.night = create_shift(
            actor=self.owner,
            organization=self.organization,
            calendar=self.calendar,
            code="NIGHT",
            name="شب",
            starts_at=time(20),
            ends_at=time(4),
            crosses_midnight=True,
            effective_from=self.today - timedelta(days=60),
            breaks=[],
        )

    def _create(self, **changes):
        data = {
            "actor": self.owner,
            "organization": self.organization,
            "relationship": self.relationship,
            "effective_from": self.today,
            "effective_to": self.today + timedelta(days=14),
            "rotation_anchor": self.today,
            "rotation": [(self.day, 2), (self.night, 1)],
            "overrides": [],
            "reason": "برنامه صریح منبع",
        }
        return service.create_roster_version(**(data | changes))

    def _planned(self, roster, days=0):
        return service.planned_shift(
            actor=self.owner,
            organization=self.organization,
            roster_id=roster.pk,
            on_date=self.today + timedelta(days=days),
        )

    def test_explicit_rotation_is_planned_separately_from_attendance(self):
        before = AttendanceRecord.objects.count()
        roster = self._create()
        self.assertEqual(
            [self._planned(roster, d)["id"] for d in range(4)],
            [str(self.day.pk), str(self.day.pk), str(self.night.pk), str(self.day.pk)],
        )
        self.assertEqual(AttendanceRecord.objects.count(), before)
        self.assertEqual(roster.relationship_id, self.relationship.pk)
        self.assertEqual(roster.version, 1)

    def test_override_and_source_snapshot_are_explicit_and_immutable(self):
        roster = self._create(overrides=[(self.today, self.night)])
        before = deepcopy(self._planned(roster))
        self.night.starts_at = time(21)
        self.night.save()
        self.assertEqual(self._planned(roster), before)
        self.assertEqual(before["starts_at"], "20:00:00")
        self.assertTrue(before["crosses_midnight"])
        self.assertEqual(
            RosterSlot.objects.filter(roster=roster, override_date=self.today).count(),
            1,
        )

    def test_version_replacement_preserves_series_source_history_and_prior_plan(self):
        first = self._create()
        prior = list(first.slots.values())
        second = self._create(
            supersedes=first, rotation=[(self.night, 1)], reason="اصلاح صریح"
        )
        self.assertEqual(second.series_id, first.series_id)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertEqual(list(first.slots.values()), prior)
        self.assertEqual(self._planned(first)["id"], str(self.day.pk))
        self.assertEqual(self._planned(second)["id"], str(self.night.pk))
        with self.assertRaises(ValidationError):
            self._create(supersedes=first)

    def test_overlap_requires_explicit_supersession(self):
        self._create()
        with self.assertRaises(ValidationError):
            self._create()
        self.assertEqual(RosterVersion.objects.count(), 1)

    def test_invalid_period_duration_or_missing_rotation_rolls_back(self):
        cases = [
            {"rotation": []},
            {"rotation": [(self.day, 0)]},
            {"rotation": [(self.day, True)]},
            {"effective_to": self.today - timedelta(days=1)},
            {"rotation_anchor": self.today + timedelta(days=1)},
            {"overrides": [(self.today - timedelta(days=1), self.day)]},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self._create(**changes)
        self.assertEqual(RosterVersion.objects.count(), 0)
        self.assertEqual(RosterSlot.objects.count(), 0)

    def test_duplicate_override_date_rolls_back(self):
        with self.assertRaises(ValidationError):
            self._create(overrides=[(self.today, self.day), (self.today, self.night)])
        self.assertFalse(RosterVersion.objects.exists())

    def test_cross_tenant_source_context_and_view_fail_closed(self):
        other = Organization.objects.create(name="Other", slug="roster-other")
        with self.assertRaises(PermissionDenied):
            self._create(organization=other)
        roster = self._create()
        with self.assertRaises(PermissionDenied):
            service.get_roster(
                actor=self.owner, organization=other, roster_id=roster.pk
            )

    def test_project_context_requires_explicit_source_assignment(self):
        project = create_project(
            actor=self.owner, organization=self.organization, code="R22P", name="پروژه"
        )
        with self.assertRaises(ValidationError):
            self._create(project=project)
        self.assertFalse(RosterVersion.objects.exists())

    def test_explicit_episode_assignment_supports_project_and_site_scope(self):
        from apps.projects.models import ProjectSite
        from apps.workforce.models import EmployeeProjectAssignment, Person

        project = create_project(
            actor=self.owner,
            organization=self.organization,
            code="R22POS",
            name="پروژه مجاز",
        )
        site = ProjectSite.objects.create(
            organization=self.organization, project=project, code="SITE", name="کارگاه"
        )
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="R22POS",
            first_name="Fixture",
            last_name="Worker",
        )
        person = Person.objects.create(
            organization=self.organization, first_name="Fixture", last_name="Worker"
        )
        relationship = self._relationship(person, "R22POS", legacy=employee)
        EmployeeProjectAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            project=project,
            site=site,
            start_date=relationship.effective_start,
            created_by=self.owner,
        )
        roster = self._create(relationship=relationship, project=project, site=site)
        self.assertEqual(roster.project_id, project.pk)
        self.assertEqual(roster.site_id, site.pk)
        self.assertEqual(self._planned(roster)["id"], str(self.day.pk))

    def test_inactive_or_out_of_period_shift_and_calendar_are_rejected(self):
        self.day.effective_to = self.today - timedelta(days=1)
        self.day.save()
        with self.assertRaises(ValidationError):
            self._create()
        self.day.effective_to = None
        self.day.save()
        self.calendar.is_active = False
        self.calendar.archived_at = timezone.now()
        self.calendar.save()
        with self.assertRaises(ValidationError):
            self._create()
        self.assertFalse(RosterVersion.objects.exists())

    def test_capability_and_object_scope_are_rechecked(self):
        permission = BusinessPermission.objects.get(code=P.ROSTERS_MANAGE)
        self.member.role_definition.permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            self._create()
        self.member.role_definition.permissions.add(permission)
        self.member.scope_grants.all().delete()
        with self.assertRaises(PermissionDenied):
            self._create()

    def test_history_cannot_be_mutated_or_deleted(self):
        roster = self._create()
        slot = roster.slots.first()
        for item in (roster, slot):
            with self.assertRaises(ValidationError):
                item.save()
            with self.assertRaises(ValidationError):
                item.delete()
            with self.assertRaises(ValidationError):
                type(item).objects.filter(pk=item.pk).delete()
        self.assertEqual(RosterVersion.objects.count(), 1)

    def test_planned_date_outside_source_version_fails(self):
        roster = self._create()
        with self.assertRaises(ValidationError):
            self._planned(roster, 15)

    def test_shift_row_remains_protected_by_history(self):
        from django.db.models.deletion import ProtectedError

        self._create()
        with self.assertRaises(ProtectedError):
            ShiftDefinition.objects.get(pk=self.day.pk).delete()

    def test_existing_attendance_and_future_plan_are_preserved_when_employment_ends(
        self,
    ):
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="ATT22",
            first_name="Fixture",
            last_name="Worker",
        )
        AttendanceRecord.objects.create(
            organization=self.organization,
            employee=employee,
            calendar=self.calendar,
            shift=self.day,
            work_date=self.today,
            check_in_at=timezone.now(),
            source="manual",
            captured_by=self.owner,
        )
        before = list(AttendanceRecord.objects.values())
        roster = self._create()
        plan = list(RosterSlot.objects.filter(roster=roster).values())
        end_work_relationship(
            actor=self.owner,
            organization=self.organization,
            relationship=self.relationship,
            effective_end=self.today,
        )
        self.assertEqual(list(AttendanceRecord.objects.values()), before)
        self.assertEqual(list(RosterSlot.objects.filter(roster=roster).values()), plan)
        self.assertEqual(self._planned(roster, 2)["id"], str(self.night.pk))

    def test_foreign_shift_and_forged_project_instances_are_reloaded_with_tenant(self):
        from apps.projects.models import Project

        from .models import WorkCalendar

        other = Organization.objects.create(name="Other", slug="roster-foreign")
        calendar = WorkCalendar.objects.create(
            organization=other,
            code="OTHER",
            name="Other",
            timezone=other.timezone,
            effective_from=self.today - timedelta(days=1),
            working_weekdays=[1],
            created_by=self.owner,
        )
        shift = ShiftDefinition.objects.create(
            organization=other,
            calendar=calendar,
            code="OTHER",
            name="Other",
            starts_at=time(8),
            ends_at=time(16),
            effective_from=self.today,
            created_by=self.owner,
        )
        with self.assertRaises(PermissionDenied):
            self._create(rotation=[(shift, 1)])
        project = Project.objects.create(
            organization=other, code="OTHER", name="Other", created_by=self.owner
        )
        project.organization_id = self.organization.pk
        with self.assertRaises(PermissionDenied):
            self._create(project=project)
        self.assertFalse(RosterVersion.objects.exists())
