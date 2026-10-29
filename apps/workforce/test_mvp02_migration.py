"""Exercise additive migration and permission recovery with historical models."""

from datetime import date
from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner


class FieldWorkforceMigrationTests(TransactionTestCase):
    def test_additive_field_preserves_legacy_and_explicit_identity_links(self):
        owner = User.objects.create_user(username="mvp02-migration-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمایش مهاجرت", slug="mvp02-migration"
        )
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [("workforce", "0015_cep029_identity_migration")]
        try:
            executor.migrate(previous)
            old_apps = executor.loader.project_state(previous).apps
            Employee = old_apps.get_model("workforce", "Employee")
            Person = old_apps.get_model("workforce", "Person")
            Relationship = old_apps.get_model("workforce", "WorkRelationship")
            legacy = Employee.objects.create(
                organization_id=organization.pk,
                employee_number="OLD-001",
                first_name="نیروی",
                last_name="قدیمی",
                user_id=owner.pk,
            )
            person = Person.objects.create(
                organization_id=organization.pk,
                first_name="نیروی",
                last_name="قدیمی",
                user_id=owner.pk,
            )
            relation = Relationship.objects.create(
                organization_id=organization.pk,
                person_id=person.pk,
                legacy_employee_id=legacy.pk,
                employee_number="OLD-001",
                effective_start=date(2026, 1, 1),
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            current = executor.loader.project_state(latest).apps
            migrated = current.get_model("workforce", "Person").objects.get(
                pk=person.pk
            )
            self.assertIsNone(migrated.national_id)
            self.assertEqual(
                (migrated.first_name, migrated.last_name, migrated.user_id),
                ("نیروی", "قدیمی", owner.pk),
            )
            linked = current.get_model("workforce", "WorkRelationship").objects.get(
                pk=relation.pk
            )
            self.assertEqual(
                (linked.person_id, linked.legacy_employee_id, linked.effective_start),
                (person.pk, legacy.pk, date(2026, 1, 1)),
            )
            self.assertIsNone(
                current.get_model("workforce", "Employee")
                .objects.get(pk=legacy.pk)
                .hire_date
            )
            # Reverse/forward remains additive: no inferred ID/backfill on recovery.
            MigrationExecutor(connection).migrate(previous)
            MigrationExecutor(connection).migrate(latest)
            self.assertIsNone(
                current.get_model("workforce", "Person")
                .objects.get(pk=person.pk)
                .national_id
            )
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_permission_reverse_forward_reactivates_without_granting_custom_roles(self):
        from django.apps import apps

        from apps.organizations.models import BusinessPermission, OrganizationRole

        owner = User.objects.create_user(username="mvp02-permission-migration")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمایش مجوز", slug="mvp02-permission-migration"
        )
        role = OrganizationRole.objects.create(
            organization=organization, code="mvp02-custom", name="نقش سفارشی"
        )
        role.permissions.add(BusinessPermission.objects.get(code="employees.create"))
        migration = import_module(
            "apps.organizations.migrations.0125_mvp02_field_workforce_permission"
        )
        with connection.schema_editor() as editor:
            migration.reverse(apps, editor)
            self.assertFalse(
                BusinessPermission.objects.get(code=migration.CODE).is_active
            )
            migration.forward(apps, editor)
        self.assertTrue(BusinessPermission.objects.get(code=migration.CODE).is_active)
        self.assertFalse(role.permissions.filter(code=migration.CODE).exists())
        self.assertTrue(
            OrganizationRole.objects.filter(
                organization__isnull=True,
                code="tenant_owner",
                permissions__code=migration.CODE,
            ).exists()
        )
