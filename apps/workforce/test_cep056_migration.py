from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.organizations.models import Organization, OrganizationSettings

from .models import (
    Employee,
    HRCertificateRequest,
    HRCertificateType,
    Person,
    WorkRelationship,
)


class CertificateMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_rollback_reapply_preserves_existing_workforce_contacts_and_identity(self):
        organization = Organization.objects.create(
            name="CEP056", slug="cep056-migration"
        )
        OrganizationSettings.objects.create(organization=organization)
        employee = Employee.objects.create(
            organization=organization,
            employee_number="M56",
            first_name="نمونه",
            last_name="آزمون",
            email="fixture@example.invalid",
            phone_number="02100000000",
            address="نشانی نمونه",
            emergency_contact="تماس نمونه",
        )
        person = Person.objects.create(
            organization=organization, first_name="نمونه", last_name="آزمون"
        )
        relationship = WorkRelationship.objects.create(
            organization=organization,
            person=person,
            legacy_employee=employee,
            employee_number="M56",
            effective_start=date(2026, 1, 1),
        )
        fields = (
            "email",
            "phone_number",
            "address",
            "emergency_contact",
            "employee_number",
        )
        before = Employee.objects.filter(pk=employee.pk).values(*fields).get()
        previous = [("workforce", "0011_cep055_personal_data_change")]
        current = [("workforce", "0012_cep056_certificate_framework")]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertEqual(
                Employee.objects.filter(pk=employee.pk).values(*fields).get(), before
            )
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(
                Employee.objects.filter(pk=employee.pk).values(*fields).get(), before
            )
            restored = WorkRelationship.objects.get(pk=relationship.pk)
            self.assertEqual(
                (restored.person_id, restored.legacy_employee_id),
                (person.pk, employee.pk),
            )
            self.assertEqual(HRCertificateType.objects.count(), 0)
            self.assertEqual(HRCertificateRequest.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(current)
