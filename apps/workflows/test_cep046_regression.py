"""Legacy runtime/workbench scenarios with explicit current fixture authority."""

from unittest.mock import patch

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.organizations.models import OrganizationMembership

from . import test_runtime, test_workbench


class ExplicitMembershipFixture:
    def setUp(self):
        original_save = OrganizationMembership.save
        manager = OrganizationMembership.objects
        original_bulk_create = manager.bulk_create

        def assigned_save(membership, *args, **kwargs):
            creating = membership._state.adding
            result = original_save(membership, *args, **kwargs)
            if creating:
                explicit_fixture_authority(membership, membership.role_definition)
            return result

        def assigned_bulk_create(*args, **kwargs):
            created = original_bulk_create(*args, **kwargs)
            for membership in created:
                explicit_fixture_authority(membership, membership.role_definition)
            return created

        for patcher in (
            patch.object(OrganizationMembership, "save", assigned_save),
            patch.object(manager, "bulk_create", assigned_bulk_create),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        super().setUp()


class RuntimeRegression(ExplicitMembershipFixture, test_runtime.WorkflowRuntimeTests):
    pass


class WorkbenchRegression(ExplicitMembershipFixture, test_workbench.WorkbenchTests):
    pass
