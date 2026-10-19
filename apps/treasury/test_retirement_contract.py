"""Destructive contract boundaries and migration-only compatibility."""

import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from apps.organizations.models import BusinessPermission, BusinessPermissionCode

contract = import_module("apps.billing.migrations.0018_retire_legacy_claim_settlements")


class RetirementContractGuardTests(SimpleTestCase):
    @override_settings(SETTINGS_MODULE="config.settings.production")
    def test_production_rejected_before_any_database_access(self):
        editor = SimpleNamespace(
            connection=SimpleNamespace(settings_dict={"HOST": "localhost"})
        )
        with self.assertRaisesMessage(RuntimeError, "Development only"):
            contract.verify_retirement(None, editor)

    def test_remote_database_rejected_before_any_database_access(self):
        editor = SimpleNamespace(
            connection=SimpleNamespace(settings_dict={"HOST": "remote.invalid"})
        )
        with self.assertRaisesMessage(RuntimeError, "Development only"):
            contract.verify_retirement(None, editor)

    def test_existing_tenant_requires_all_twelve_and_exact_candidate(self):
        editor = SimpleNamespace(
            connection=SimpleNamespace(
                settings_dict={"HOST": "localhost", "NAME": "configured-development"},
                alias="default",
            )
        )
        historical = Mock()
        historical.get_model.return_value.objects.using.return_value.exists.return_value = True
        with (
            TemporaryDirectory() as tmp,
            override_settings(
                BASE_DIR=Path(tmp), SETTINGS_MODULE="config.settings.development"
            ),
        ):
            path = (
                Path(tmp)
                / "docs/governance/cep/evidence/CEP-064_RETIREMENT_READINESS.json"
            )
            path.parent.mkdir(parents=True)
            for conditions, digest in (
                (
                    [
                        {"number": n, "status": "FAIL" if n == 11 else "PASS"}
                        for n in range(1, 13)
                    ],
                    "stale",
                ),
                ([{"number": n, "status": "PASS"} for n in range(1, 13)], "stale"),
            ):
                path.write_text(
                    json.dumps(
                        {
                            "conditions": conditions,
                            "LEGACY_PAYMENT_RETIREMENT_READINESS": "PASS",
                            "candidate_digest": digest,
                        }
                    )
                )
                with self.assertRaisesMessage(RuntimeError, "twelve-condition"):
                    contract.verify_retirement(historical, editor)


class RetiredRuntimeContractTests(TestCase):
    def test_legacy_schema_and_permissions_absent_but_treasury_remains(self):
        tables = set(connection.introspection.table_names())
        self.assertFalse(
            tables
            & {
                "payments_payment",
                "payments_paymentallocation",
                "payments_paymentdocumentlink",
                "billing_claimsettlementallocation",
            }
        )
        self.assertTrue(
            {
                "treasury_paymentrequest",
                "treasury_treasurymovement",
                "subledgers_settlementallocation",
                "documents_retiredpaymentevidence",
            }
            <= tables
        )
        self.assertEqual(list(apps.get_app_config("payments").get_models()), [])
        self.assertFalse(
            any(code.startswith("payments.") for code in BusinessPermissionCode.values)
        )
        self.assertFalse(
            BusinessPermission.objects.filter(code__startswith="payments.").exists()
        )
