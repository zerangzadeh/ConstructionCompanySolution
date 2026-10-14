from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner
from apps.workforce.models import (
    Employee,
    Person,
    WorkRelationship,
    WorkRelationshipRevision,
)
from apps.workforce.person_services import (
    create_person,
    create_work_relationship,
    end_work_relationship,
    resolve_legacy_employee,
)


class PersonWorkRelationshipTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="cep010-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="CEP010", slug="cep010"
        )
        self.other_owner = User.objects.create_user(username="cep010-other")
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="CEP010 Other", slug="cep010-other"
        )
        self.person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="First",
            last_name="Worker",
        )

    def _episode(
        self,
        *,
        start: date = date(2025, 1, 1),
        end: date | None = None,
        employee_number: str = "EMP-001",
        legacy_employee: Employee | None = None,
    ) -> WorkRelationship:
        return create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=self.person,
            employee_number=employee_number,
            effective_start=start,
            effective_end=end,
            legacy_employee=legacy_employee,
        )

    def test_person_stable_identity_and_optional_user(self) -> None:
        self.assertIsNone(self.person.user)
        first = self._episode(end=date(2025, 6, 30))
        second = self._episode(start=date(2025, 7, 1))
        self.assertEqual(first.person_id, second.person_id)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.person.pk, Person.objects.get(pk=self.person.pk).pk)
        self.assertEqual(
            WorkRelationshipRevision.objects.filter(
                relationship__person=self.person
            ).count(),
            2,
        )

    def test_user_link_requires_active_same_tenant_membership(self) -> None:
        linked = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Linked",
            last_name="Worker",
            user=self.owner,
        )
        self.assertEqual(linked.user_id, self.owner.pk)
        with self.assertRaises(ValidationError):
            create_person(
                organization=self.organization,
                actor=self.owner,
                first_name="Foreign",
                last_name="User",
                user=self.other_owner,
            )

    def test_end_is_versioned_and_history_is_immutable(self) -> None:
        episode = self._episode()
        first_revision = episode.revisions.get(version=1)
        ended = end_work_relationship(
            organization=self.organization,
            actor=self.owner,
            relationship=episode,
            effective_end=date(2025, 8, 1),
        )
        self.assertEqual(ended.effective_end, date(2025, 8, 1))
        self.assertIsNone(first_revision.effective_end)
        self.assertEqual(
            episode.revisions.get(version=2).effective_end, date(2025, 8, 1)
        )
        first_revision.effective_end = date(2025, 1, 2)
        with self.assertRaises(ValidationError):
            first_revision.save()
        with self.assertRaises(ValidationError):
            end_work_relationship(
                organization=self.organization,
                actor=self.owner,
                relationship=ended,
                effective_end=date(2025, 9, 1),
            )

    def test_invalid_dates_and_overlap_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._episode(start=date(2025, 2, 1), end=date(2025, 1, 1))
        self._episode(end=date(2025, 6, 30))
        with self.assertRaises(ValidationError):
            self._episode(start=date(2025, 6, 30), end=date(2025, 8, 1))
        self._episode(start=date(2025, 7, 1))

    def test_database_date_constraint(self) -> None:
        episode = self._episode()
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkRelationship.objects.filter(pk=episode.pk).update(
                effective_end=date(2024, 1, 1)
            )

    def test_cross_tenant_person_and_legacy_rejected(self) -> None:
        other_person = create_person(
            organization=self.other_organization,
            actor=self.other_owner,
            first_name="Other",
            last_name="Person",
        )
        with self.assertRaises(PermissionDenied):
            create_work_relationship(
                organization=self.organization,
                actor=self.owner,
                person=other_person,
                employee_number="EMP-002",
                effective_start=date(2025, 1, 1),
            )
        other_employee = Employee.objects.create(
            organization=self.other_organization,
            employee_number="EMP-003",
            first_name="Other",
            last_name="Employee",
        )
        with self.assertRaises(PermissionDenied):
            self._episode(employee_number="EMP-003", legacy_employee=other_employee)

    def test_direct_model_references_reject_cross_tenant(self) -> None:
        other_person = create_person(
            organization=self.other_organization,
            actor=self.other_owner,
            first_name="Other",
            last_name="Person",
        )
        with self.assertRaises(ValidationError):
            WorkRelationship(
                organization=self.organization,
                person=other_person,
                employee_number="EMP-002",
                effective_start=date(2025, 1, 1),
            ).save()

    def test_legacy_employee_remains_addressable_without_backfill(self) -> None:
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-001",
            first_name="Legacy",
            last_name="Employee",
        )
        before = legacy.pk
        self.assertEqual(
            resolve_legacy_employee(
                organization=self.organization,
                actor=self.owner,
                employee=legacy,
            ),
            (legacy, None),
        )
        self.assertFalse(WorkRelationship.objects.exists())
        self.assertEqual(Employee.objects.get(pk=before).employee_number, "EMP-001")
        episode = self._episode(legacy_employee=legacy)
        self.assertEqual(
            resolve_legacy_employee(
                organization=self.organization,
                actor=self.owner,
                employee=legacy,
            ),
            (legacy, episode),
        )
        self.assertEqual(Employee.objects.get(pk=before).employee_number, "EMP-001")

    def test_ambiguous_legacy_mapping_fails_closed(self) -> None:
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-001",
            first_name="Legacy",
            last_name="Employee",
        )
        self._episode(end=date(2025, 6, 30), legacy_employee=legacy)
        self._episode(start=date(2025, 7, 1), legacy_employee=legacy)
        with self.assertRaises(ValidationError):
            resolve_legacy_employee(
                organization=self.organization,
                actor=self.owner,
                employee=legacy,
            )

    def test_legacy_employee_cannot_change_person_identity(self) -> None:
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-001",
            first_name="Legacy",
            last_name="Employee",
        )
        self._episode(end=date(2025, 6, 30), legacy_employee=legacy)
        another_person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Another",
            last_name="Person",
        )
        with self.assertRaises(ValidationError):
            create_work_relationship(
                organization=self.organization,
                actor=self.owner,
                person=another_person,
                employee_number="EMP-001",
                effective_start=date(2025, 7, 1),
                legacy_employee=legacy,
            )

    def test_episode_identity_and_history_cannot_be_rewritten(self) -> None:
        episode = self._episode()
        episode.employee_number = "CHANGED"
        with self.assertRaises(ValidationError):
            episode.save()
        with self.assertRaises(ValidationError):
            episode.delete()
        with self.assertRaises(ValidationError):
            episode.revisions.get(version=1).delete()

    def test_no_job_family_or_grade_architecture(self) -> None:
        self.assertFalse(hasattr(self.person, "job_family"))
        self.assertFalse(hasattr(WorkRelationship, "job_grade"))
