"""Bounded MVP-04E validation on its migrated, reusable isolated PostgreSQL DB."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner

from apps.billing.test_mvp03_browser import ContractBillingBrowserTests
from apps.procurement.test_mvp04b_scope import (
    LegacyScopeMigrationTests,
    ScopeConcurrencyTests,
)
from apps.procurement.test_p5_s08_sealed_custody import SealedCustodyConcurrencyTests
from apps.procurement.test_p5_s10_admissibility import AdmissibilityFixtureMixin
from apps.procurement.test_p5_s11_comparison_award import (
    P5S11ConcurrencyTests,
    P5S11TwoRevisionFixtureMixin,
)
from apps.procurement.test_rfq import RequestForQuotationConcurrencyTests
from apps.procurement.test_rfq_close import RFQCloseConcurrencyTests


# Existing historical helpers express a role but predate explicit assignments.
def assigned_actor(original):
    def wrapped(self, *args, **kwargs):
        actor = original(self, *args, **kwargs)
        self.establish_test_membership_authority(
            self.organization.memberships.get(user=actor)
        )
        return actor

    return wrapped


for fixture in (AdmissibilityFixtureMixin, P5S11TwoRevisionFixtureMixin):
    fixture._make_actor = assigned_actor(fixture._make_actor)
from apps.procurement.test_quotes import SealedQuoteConcurrencyTests
from apps.procurement.test_p5_s09_protected_opening import ProtectedOpeningConcurrencyTests
from apps.procurement.test_p5_s10_admissibility import QuoteAdmissibilityConcurrencyTests

for case in (
    SealedQuoteConcurrencyTests, ProtectedOpeningConcurrencyTests, QuoteAdmissibilityConcurrencyTests,
    SealedCustodyConcurrencyTests,
    P5S11ConcurrencyTests,
    RequestForQuotationConcurrencyTests,
    RFQCloseConcurrencyTests,
    LegacyScopeMigrationTests,
    ScopeConcurrencyTests,
):
    case._fixture_teardown = ContractBillingBrowserTests._fixture_teardown
    case.serialized_rollback = True
from apps.inventory.test_cep034_receipt_contract import ReceiptContractConcurrencyTests
ReceiptContractConcurrencyTests._fixture_teardown = ContractBillingBrowserTests._fixture_teardown
ReceiptContractConcurrencyTests.serialized_rollback = True

name = Path("output/mvp-04e/database-name.txt").read_text(encoding="utf-8").strip()
assert name.startswith("test_mvp04e_")
settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = name
print("Isolated validation DB:", name, flush=True)
print(
    "Fixture-only adaptations: explicit actor assignments and guarded CASCADE cleanup",
    flush=True,
)
labels = sys.argv[1:] or [
    "apps.inventory.test_mvp04e",
    "apps.procurement.test_mvp04d",
    "apps.inventory.test_cep034_receipt_contract",
]

raise SystemExit(
    bool(DiscoverRunner(verbosity=1, interactive=False, keepdb=True).run_tests(labels))
)
