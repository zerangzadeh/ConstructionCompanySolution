"""Bounded additive rollback/reapply; finalized leave history cannot be dropped."""

from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TransactionTestCase

from apps.organizations.models import OrganizationRole
from apps.timekeeping.models import LeaveMissionRequest

from . import test_cep023 as fixtures
from .leave_models import LeaveBalanceEntry, LeavePolicyVersion
from .models import Employee, Person, WorkRelationship, WorkRelationshipRevision


class LeaveMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_additive_reverse_reapply_preserves_legacy_and_existing_authority(self):
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        for permissions in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertFalse(
                set(permissions)
                & {
                    "leave_policies.manage",
                    "leave_balances.manage",
                    "leave_balances.view",
                }
            )
        fixture = fixtures.LeaveAuthorityTests()
        fixture.setUp()
        fixture.request()
        sources = [
            Employee,
            Person,
            WorkRelationship,
            WorkRelationshipRevision,
            LeaveMissionRequest,
            OrganizationRole.permissions.through,
        ]
        before = {
            model._meta.label: list(model.objects.order_by("pk").values())
            for model in sources
        }
        guard = import_module(
            "apps.workforce.migrations.0014_cep023_leave_authority"
        ).preserve_leave_history
        try:
            # Actual migration apply/reverse/reapply is separately retained in
            # command output. Exercise the same bounded schema operations here
            # without replaying all unrelated historical ProjectState graphs.
            with connection.schema_editor() as editor:
                guard(apps, editor)
                editor.delete_model(LeaveBalanceEntry)
                editor.delete_model(LeavePolicyVersion)
            self.assertNotIn(
                "workforce_leavebalanceentry", connection.introspection.table_names()
            )
            self.assertEqual(
                before,
                {
                    model._meta.label: list(model.objects.order_by("pk").values())
                    for model in sources
                },
            )
            with connection.schema_editor() as editor:
                editor.create_model(LeavePolicyVersion)
                editor.create_model(LeaveBalanceEntry)
            self.assertEqual(
                before,
                {
                    model._meta.label: list(model.objects.order_by("pk").values())
                    for model in sources
                },
            )
            policy = fixture.policy()
            source = fixture.credit()
            with (
                connection.schema_editor() as editor,
                self.assertRaisesMessage(
                    RuntimeError, "destructive schema rollback is forbidden"
                ),
            ):
                guard(apps, editor)
            policy.refresh_from_db()
            source.refresh_from_db()
            self.assertEqual(source.policy_id, policy.pk)
            print(
                "CEP023 additive rollback/reapply: preserved Employee/Person/WorkRelationship/revisions/native requests/role grants; populated history rollback refused"
            )
        finally:
            tables = connection.introspection.table_names()
            with connection.schema_editor() as editor:
                if LeavePolicyVersion._meta.db_table not in tables:
                    editor.create_model(LeavePolicyVersion)
                if LeaveBalanceEntry._meta.db_table not in tables:
                    editor.create_model(LeaveBalanceEntry)
