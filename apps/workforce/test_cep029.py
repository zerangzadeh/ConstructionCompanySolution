"""CEP-029 conversion, reconciliation, preservation and rollback evidence."""

from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)

from . import identity_migration as service
from . import test_cep010_person_workrelationship as fixtures
from .identity_migration_models import EmployeeIdentityMigration
from .models import (
    Employee,
    EmployeeProjectAssignment,
    Person,
    WorkRelationship,
    WorkRelationshipRevision,
)
from .person_services import create_work_relationship


class IdentityMigrationTests(TestCase):
    setUp = fixtures.PersonWorkRelationshipTests.setUp

    def employee(self, **changes):
        return Employee.objects.create(
            **(
                {
                    "organization": self.organization,
                    "employee_number": "M1",
                    "first_name": "Synthetic",
                    "last_name": "Worker",
                    "hire_date": date(2026, 1, 1),
                }
                | changes
            )
        )

    def run_migration(self, **changes):
        return service.migrate_employee_identities(
            **(
                {
                    "organization": self.organization,
                    "actor": self.owner,
                    "source_key": "test-source-v1",
                    "reason": "Explicit non-production identity migration",
                }
                | changes
            )
        )

    def test_source_mapping_counts_lineage_and_repeatability(self):
        employee = self.employee()
        before = list(Employee.objects.values())
        result = self.run_migration()
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["mapped_count"], 1)
        self.assertEqual(result["exception_count"], 0)
        row = result["mapping"][0]
        target = WorkRelationship.objects.get(pk=row["relationship_id"])
        self.assertEqual(target.legacy_employee_id, employee.pk)
        self.assertEqual(target.employee_number, employee.employee_number)
        self.assertEqual(target.effective_start, employee.hire_date)
        self.assertIsNone(target.person.user_id)
        self.assertEqual(list(Employee.objects.values()), before)
        repeated = self.run_migration()
        self.assertTrue(repeated["repeated"])
        self.assertEqual(repeated["mapping"], result["mapping"])
        self.assertEqual(WorkRelationship.objects.count(), 1)
        self.assertEqual(EmployeeIdentityMigration.objects.count(), 1)
        second = self.run_migration(source_key="new-source-checkpoint")
        self.assertEqual(second["mapping"][0]["status"], "EXISTING")
        self.assertEqual(
            second["mapping"][0]["relationship_id"], row["relationship_id"]
        )

    def test_rehearsal_rollback_then_apply_then_retry(self):
        self.employee()
        before = service._counts(self.organization)
        rehearsal = self.run_migration(rehearsal=True)
        self.assertEqual(rehearsal["mapped_count"], 1)
        self.assertEqual(service._counts(self.organization), before)
        self.assertEqual(EmployeeIdentityMigration.objects.count(), 0)
        applied = self.run_migration()
        self.assertEqual(applied["before"], before)
        self.assertEqual(applied["mapped_count"], rehearsal["mapped_count"])
        self.assertTrue(self.run_migration()["repeated"])

    def test_missing_dates_and_undated_inactive_history_are_exceptions(self):
        a = self.employee(hire_date=None)
        b = self.employee(employee_number="M2", status="inactive")
        result = self.run_migration()
        self.assertEqual(
            (result["source_count"], result["mapped_count"], result["exception_count"]),
            (2, 0, 2),
        )
        self.assertEqual(
            {row["employee_id"] for row in result["exceptions"]}, {str(a.pk), str(b.pk)}
        )
        self.assertEqual(
            {row["code"] for row in result["exceptions"]},
            {
                "MISSING_EFFECTIVE_HIRE_DATE",
                "NONACTIVE_EPISODE_HAS_NO_DATED_END_EVIDENCE",
            },
        )
        self.assertEqual(WorkRelationship.objects.count(), 0)

    def test_explicit_dated_sources_reconstruct_rehire_without_rewriting(self):
        first = self.employee(status="terminated", termination_date=date(2026, 3, 31))
        second = self.employee(employee_number="M2", hire_date=date(2026, 4, 1))
        result = self.run_migration(
            explicit_person_mapping={
                str(first.pk): str(self.person.pk),
                str(second.pk): str(self.person.pk),
            }
        )
        self.assertEqual(result["mapped_count"], 2)
        self.assertEqual(
            {row["person_id"] for row in result["mapping"]}, {str(self.person.pk)}
        )
        episodes = list(WorkRelationship.objects.order_by("effective_start"))
        self.assertEqual(
            (episodes[0].effective_end, episodes[1].effective_start),
            (date(2026, 3, 31), date(2026, 4, 1)),
        )
        self.assertNotEqual(episodes[0].pk, episodes[1].pk)
        self.assertEqual(WorkRelationshipRevision.objects.count(), 2)

    def test_undated_rehire_transition_is_not_fabricated(self):
        employee = self.employee()
        record_audit_event(
            organization=self.organization,
            actor=self.owner,
            action=AuditAction.EMPLOYEE_STATUS_CHANGED,
            entity_type="employee",
            entity_id=str(employee.pk),
            metadata={"previous_status": "terminated", "new_status": "active"},
        )
        result = self.run_migration()
        self.assertEqual(
            result["exceptions"][0]["code"],
            "REHIRE_HISTORY_REQUIRES_SEPARATE_DATED_SOURCE_EPISODES",
        )
        self.assertEqual(WorkRelationship.objects.count(), 0)

    def test_existing_person_relationship_and_revision_facts_preserved(self):
        employee = self.employee()
        target = create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=self.person,
            employee_number=employee.employee_number,
            effective_start=employee.hire_date,
            legacy_employee=employee,
        )
        before = {
            m._meta.label: list(m.objects.order_by("pk").values())
            for m in [Person, WorkRelationship, WorkRelationshipRevision]
        }
        result = self.run_migration()
        self.assertEqual(result["mapping"][0]["relationship_id"], str(target.pk))
        self.assertEqual(result["mapping"][0]["status"], "EXISTING")
        self.assertEqual(
            before,
            {
                m._meta.label: list(m.objects.order_by("pk").values())
                for m in [Person, WorkRelationship, WorkRelationshipRevision]
            },
        )

    def test_conflicting_existing_episode_is_exception_and_no_orphan(self):
        employee = self.employee()
        create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=self.person,
            employee_number=employee.employee_number,
            effective_start=date(2025, 1, 1),
            legacy_employee=employee,
        )
        counts = service._counts(self.organization)
        result = self.run_migration()
        self.assertEqual(result["exception_count"], 1)
        self.assertEqual(service._counts(self.organization), counts)

    def test_overlapping_rehire_sources_create_explicit_exception(self):
        first = self.employee()
        second = self.employee(employee_number="M2", hire_date=date(2026, 2, 1))
        result = self.run_migration(
            explicit_person_mapping={
                str(first.pk): str(self.person.pk),
                str(second.pk): str(self.person.pk),
            }
        )
        self.assertEqual((result["mapped_count"], result["exception_count"]), (1, 1))
        self.assertEqual(WorkRelationship.objects.count(), 1)

    def test_failed_run_rolls_back_all_targets_and_evidence(self):
        self.employee()
        before = service._counts(self.organization)
        with (
            patch.object(
                EmployeeIdentityMigration.objects,
                "create",
                side_effect=RuntimeError("simulated durable reconciliation failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.run_migration()
        self.assertEqual(service._counts(self.organization), before)
        self.assertEqual(EmployeeIdentityMigration.objects.count(), 0)

    def test_tenant_boundaries_permissions_and_suspension(self):
        employee = self.employee()
        foreign_person = Person.objects.create(
            organization=self.other_organization, first_name="Other", last_name="Person"
        )
        for kwargs in [
            {"actor": self.other_owner},
            {"explicit_person_mapping": {str(employee.pk): str(foreign_person.pk)}},
            {"explicit_person_mapping": {str(foreign_person.pk): str(self.person.pk)}},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(PermissionDenied):
                self.run_migration(**kwargs)
        Organization.objects.filter(pk=self.organization.pk).update(status="suspended")
        with self.assertRaises(PermissionDenied):
            self.run_migration()
        self.assertEqual(EmployeeIdentityMigration.objects.count(), 0)

    def test_explicit_user_source_does_not_grant_workforce_access(self):
        employee = self.employee(user=self.owner)
        result = self.run_migration()
        target = WorkRelationship.objects.get(
            pk=result["mapping"][0]["relationship_id"]
        )
        self.assertIsNone(target.person.user_id)
        employee.refresh_from_db()
        self.assertEqual(employee.user_id, self.owner.pk)

    def test_changed_source_or_mapping_key_fails_without_mutation(self):
        employee = self.employee()
        self.run_migration()
        before = service._counts(self.organization)
        employee.first_name = "Source correction"
        employee.save()
        with self.assertRaises(ValidationError):
            self.run_migration()
        self.assertEqual(service._counts(self.organization), before)

    def test_run_history_is_immutable(self):
        self.employee()
        result = self.run_migration()
        run = EmployeeIdentityMigration.objects.get(pk=result["run_id"])
        for operation in [
            lambda: run.save(),
            lambda: run.delete(),
            lambda: EmployeeIdentityMigration.objects.update(reason="overwrite"),
            lambda: EmployeeIdentityMigration.objects.all().delete(),
        ]:
            with self.assertRaises(ValidationError):
                operation()

    def test_assignment_sources_are_preserved_and_never_transferred(self):
        employee = self.employee()
        from apps.projects.models import Project

        project = Project.objects.create(
            organization=self.organization,
            code="MIG",
            name="Migration",
            created_by=self.owner,
        )
        assignment = EmployeeProjectAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            project=project,
            start_date=date(2026, 1, 2),
            created_by=self.owner,
        )
        before = list(EmployeeProjectAssignment.objects.values())
        result = self.run_migration()
        self.assertTrue(result["source_and_assignments_preserved"])
        self.assertEqual(list(EmployeeProjectAssignment.objects.values()), before)
        assignment.refresh_from_db()
        self.assertEqual(assignment.employee_id, employee.pk)

    def test_no_inferred_merge_of_similar_names(self):
        first = self.employee()
        second = self.employee(employee_number="M2")
        result = self.run_migration()
        self.assertEqual(result["mapped_count"], 2)
        self.assertEqual(len({row["person_id"] for row in result["mapping"]}), 2)
        self.assertNotEqual(first.pk, second.pk)

    def test_retry_detects_target_history_drift_without_rewriting(self):
        self.employee()
        result = self.run_migration()
        target = WorkRelationship.objects.get(
            pk=result["mapping"][0]["relationship_id"]
        )
        from .person_services import end_work_relationship

        end_work_relationship(
            organization=self.organization,
            actor=self.owner,
            relationship=target,
            effective_end=date(2026, 3, 31),
        )
        before = list(WorkRelationshipRevision.objects.order_by("pk").values())
        with self.assertRaises(ValidationError):
            self.run_migration()
        self.assertEqual(
            before, list(WorkRelationshipRevision.objects.order_by("pk").values())
        )

    def test_permission_removal_and_inactive_membership_reject_retry(self):
        self.employee()
        self.run_migration()
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        OrganizationRole.permissions.through.objects.filter(
            organizationrole__in=[
                membership.role_definition_id,
                *membership.role_assignments.values_list("role_id", flat=True),
            ],
            businesspermission__code=P.EMPLOYEES_CREATE,
        ).delete()
        with self.assertRaises(PermissionDenied):
            self.run_migration()
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=P.EMPLOYEES_CREATE)
        )
        OrganizationMembership.objects.filter(pk=membership.pk).update(
            status="suspended"
        )
        with self.assertRaises(PermissionDenied):
            self.run_migration()
