from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase

def pytest_collection_modifyitems(items):
    from apps.procurement.test_p5_s10_admissibility import AdmissibilityFixtureMixin
    from apps.inventory.test_p8_s12_s17 import InventoryValuationAcceptanceTests
    from apps.organizations.models import AuthorizationScopeType

    original_actor = AdmissibilityFixtureMixin._make_actor
    def scoped_actor(self, name):
        actor = original_actor(self, name)
        self.establish_test_membership_authority(self.organization.memberships.get(user=actor))
        return actor
    AdmissibilityFixtureMixin._make_actor = scoped_actor

    original_valuation = InventoryValuationAcceptanceTests.setUp
    def scoped_valuation(self):
        original_valuation(self)
        member = self.organization.memberships.get(user=self.transfer_reviewer)
        member.scope_grants.get_or_create(
            organization=self.organization,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            defaults={"reason":"Independent synthetic valuation receiver"},
        )
    InventoryValuationAcceptanceTests.setUp = scoped_valuation

    def safe_test_teardown(self):
        for alias in self._databases_names(include_mirrors=False):
            assert connections[alias].settings_dict["NAME"] in {"test_b06_qualified", "test_b06_final_focused"}
            call_command("flush", verbosity=0, interactive=False, database=alias,
                         reset_sequences=False, allow_cascade=True, inhibit_post_migrate=True)
    TransactionTestCase._fixture_teardown = safe_test_teardown

