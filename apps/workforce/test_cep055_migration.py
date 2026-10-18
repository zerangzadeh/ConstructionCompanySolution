from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.organizations.models import Organization, OrganizationSettings

from .models import Employee, Person, PersonalDataRequest, WorkRelationship


class PersonalChangeMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_expand_rollback_reapply_retains_legacy_contact_and_identity(self):
        organization = Organization.objects.create(
            name="CEP055", slug="cep055-migration"
        )
        OrganizationSettings.objects.create(organization=organization)
        employee = Employee.objects.create(
            organization=organization,
            employee_number="M55",
            first_name="نمونه",
            last_name="آزمون",
            email="fixture@example.invalid",
            phone_number="02100000000",
        )
        person = Person.objects.create(
            organization=organization, first_name="نمونه", last_name="آزمون"
        )
        relationship = WorkRelationship.objects.create(
            organization=organization,
            person=person,
            legacy_employee=employee,
            employee_number="M55",
            effective_start=date(2026, 1, 1),
        )
        before = (
            Employee.objects.filter(pk=employee.pk)
            .values("email", "phone_number", "employee_number")
            .get()
        )
        previous = [("workforce", "0010_workrelationshipdocumentlink")]
        current = [("workforce", "0011_cep055_personal_data_change")]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertEqual(
                Employee.objects.filter(pk=employee.pk)
                .values("email", "phone_number", "employee_number")
                .get(),
                before,
            )
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(
                Employee.objects.filter(pk=employee.pk)
                .values("email", "phone_number", "employee_number")
                .get(),
                before,
            )
            restored = WorkRelationship.objects.get(pk=relationship.pk)
            self.assertEqual(
                (restored.person_id, restored.legacy_employee_id),
                (person.pk, employee.pk),
            )
            self.assertEqual(PersonalDataRequest.objects.count(), 0)
            self.assertEqual(Employee.objects.get(pk=employee.pk).address, "")
        finally:
            MigrationExecutor(connection).migrate(current)
