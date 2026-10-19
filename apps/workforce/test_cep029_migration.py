"""Bounded schema and transactional data rollback/reapply evidence."""

from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TransactionTestCase

from . import test_cep029 as fixtures
from .identity_migration_models import EmployeeIdentityMigration
from .models import Employee, Person, WorkRelationship, WorkRelationshipRevision


class IdentitySchemaMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_additive_schema_preserves_facts_and_refuses_populated_evidence_drop(self):
        fixture = fixtures.IdentityMigrationTests()
        fixture.setUp()
        fixture.employee()
        sources = [Employee, Person, WorkRelationship, WorkRelationshipRevision]
        before = {
            m._meta.label: list(m.objects.order_by("pk").values()) for m in sources
        }
        guard = import_module(
            "apps.workforce.migrations.0015_cep029_identity_migration"
        ).preserve_migration_evidence
        try:
            with connection.schema_editor() as editor:
                guard(apps, editor)
                editor.delete_model(EmployeeIdentityMigration)
            self.assertNotIn(
                EmployeeIdentityMigration._meta.db_table,
                connection.introspection.table_names(),
            )
            with connection.schema_editor() as editor:
                editor.create_model(EmployeeIdentityMigration)
            self.assertEqual(
                before,
                {
                    m._meta.label: list(m.objects.order_by("pk").values())
                    for m in sources
                },
            )
            dry = fixture.run_migration(rehearsal=True)
            self.assertEqual(
                before,
                {
                    m._meta.label: list(m.objects.order_by("pk").values())
                    for m in sources
                },
            )
            applied = fixture.run_migration()
            self.assertEqual(dry["mapped_count"], applied["mapped_count"])
            self.assertTrue(fixture.run_migration()["repeated"])
            with (
                connection.schema_editor() as editor,
                self.assertRaisesMessage(
                    RuntimeError, "destructive rollback is forbidden"
                ),
            ):
                guard(apps, editor)
            self.assertEqual(EmployeeIdentityMigration.objects.count(), 1)
            print(
                "CEP029 bounded schema reverse/reapply preserves sources; data rehearsal rolled back, apply/retry reconciled; populated evidence drop refused"
            )
        finally:
            if (
                EmployeeIdentityMigration._meta.db_table
                not in connection.introspection.table_names()
            ):
                with connection.schema_editor() as editor:
                    editor.create_model(EmployeeIdentityMigration)
