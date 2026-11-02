"""Bounded validation harness; never targets development or production data.

The unchanged pilot test helper predates explicit effective role assignments.
The retained Payment FK needs the already-qualified isolated CASCADE cleanup.
These test-only adaptations preserve the original test assertions and services.
"""

import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.test.runner import DiscoverRunner

from apps.billing.test_mvp03_browser import ContractBillingBrowserTests
from apps.procurement.test_rfq import RequestForQuotationConcurrencyTests
from apps.procurement.test_workflow import PurchaseRequestWorkflowPilotTests

original_manager = PurchaseRequestWorkflowPilotTests._manager_with_position


def effective_manager(self, **kwargs):
    actor, membership = original_manager(self, **kwargs)
    self.establish_test_membership_authority(membership)
    return actor, membership


PurchaseRequestWorkflowPilotTests._manager_with_position = effective_manager
RequestForQuotationConcurrencyTests._fixture_teardown = (
    ContractBillingBrowserTests._fixture_teardown
)
RequestForQuotationConcurrencyTests.serialized_rollback = True
task_database = "test_mvp04a_" + uuid4().hex[:10]
assert task_database.startswith("test_mvp04a_")
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = task_database
print("Task-isolated PostgreSQL database:", task_database, flush=True)
print(
    "Fixture adaptations: explicit manager assignment; isolated CASCADE cleanup",
    flush=True,
)
labels = sys.argv[1:] or [
    "apps.procurement.test_mvp04a",
    "apps.procurement.tests",
    "apps.procurement.test_workflow",
    "apps.procurement.test_cep079_workflow_scope",
    "apps.procurement.test_rfq",
    "apps.procurement.test_cep032_workspace",
    "apps.procurement.test_mvp04a_browser",
]
raise SystemExit(bool(DiscoverRunner(verbosity=1, interactive=False).run_tests(labels)))
