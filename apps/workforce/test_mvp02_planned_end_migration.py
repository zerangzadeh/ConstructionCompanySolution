"""Prove the additive assignment column preserves existing history."""

from datetime import date

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner


class AssignmentPlannedEndMigrationTests(TransactionTestCase):
    def _fixture_teardown(self):
        # Retained state-only Payments tables require cascade during test flush.
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        call_command(
            "flush",
            verbosity=0,
            interactive=False,
            reset_sequences=False,
            allow_cascade=True,
            inhibit_post_migrate=True,
        )

    def test_legacy_active_and_ended_rows_survive_additive_migration(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        owner = User.objects.create_user(username="planned-migration-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت مهاجرت برنامه تخصیص", slug="planned-migration"
        )
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [("workforce", "0016_mvp02_person_national_id")]
        try:
            executor.migrate(previous)
            old = executor.loader.project_state(previous).apps
            project = old.get_model("projects", "Project").objects.create(
                organization_id=organization.pk, code="MIGRATION", name="پروژه"
            )
            worker = old.get_model("workforce", "Employee").objects.create(
                organization_id=organization.pk,
                employee_number="OLD",
                first_name="نیروی",
                last_name="قدیمی",
            )
            assignments = old.get_model("workforce", "EmployeeProjectAssignment")
            for status, end in (("active", None), ("completed", date(2026, 10, 5))):
                assignments.objects.create(
                    organization_id=organization.pk,
                    employee_id=worker.pk,
                    project_id=project.pk,
                    start_date=date(2026, 10, 1),
                    status=status,
                    end_date=end,
                    role_title="شرح قدیمی",
                    notes="یادداشت",
                )
            before = list(assignments.objects.order_by("pk").values())
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            current = executor.loader.project_state(latest).apps.get_model(
                "workforce", "EmployeeProjectAssignment"
            )
            after = list(current.objects.order_by("pk").values())
            self.assertTrue(all(row.pop("planned_end_date") is None for row in after))
            self.assertEqual(after, before)
        finally:
            MigrationExecutor(connection).migrate(latest)
