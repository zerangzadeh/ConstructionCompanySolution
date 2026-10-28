"""Current-source regression and complete changed-schema recovery fingerprints."""

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import django

django.setup()

from django.conf import settings
from django.db import connection
from django.test.runner import DiscoverRunner

OUT = Path("/evidence")


def main():
    assert settings.SETTINGS_MODULE == "config.settings.production"
    db = settings.DATABASES["default"]
    assert db["NAME"].startswith("pe_legacy_20261028_") and db["HOST"] == "db"
    assert db["OPTIONS"]["sslmode"] == "verify-full"
    if sys.argv[1] == "fingerprint":
        from scripts.cep070_erp_recovery_proof import fingerprint

        options = dict(
            db["OPTIONS"],
            host=db["HOST"],
            port=db["PORT"],
            user=db["USER"],
            password=db["PASSWORD"],
            options="-c timezone=UTC",
        )
        value = fingerprint(options, db["NAME"])
        value.pop("constraint_definitions")
        (OUT / (sys.argv[2] + "_FINGERPRINT.json")).write_text(
            json.dumps(value, indent=2) + "\n"
        )
    elif sys.argv[1] == "regression":
        assert db["NAME"] == "pe_legacy_20261028_empty"
        assert connection.connection is None
        settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
            "test_pe_legacy_20261028_regression"
        )
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        settings.SECURE_SSL_REDIRECT = (
            False  # Test client only; real TLS evidence retained.
        )
        labels = [
            "apps.treasury.test_retirement_contract",
            "apps.treasury.test_payment_retirement.TreasuryPaymentReplacementTests",
            "apps.billing.test_payment_retirement.TreasuryClaimSettlementTransitionTests",
            "apps.billing.test_payment_retirement.UnrecognizedClaimSettlementTests",
            "apps.reporting.test_payment_retirement.ClaimSettlementReportingTests",
        ]
        with (
            (OUT / "REGRESSION.txt").open("w") as log,
            redirect_stdout(log),
            redirect_stderr(log),
        ):
            failed = DiscoverRunner(
                verbosity=2, interactive=False, keepdb=True
            ).run_tests(labels)
        (OUT / "REGRESSION.json").write_text(
            json.dumps(
                {
                    "failed": failed,
                    "labels": labels,
                    "scope": "Affected active Treasury/AR/no-double-counting/reporting/DMS/retained-source/runtime contract",
                    "test_only_overrides": [
                        "MD5 hasher",
                        "client HTTPS redirect disabled",
                    ],
                    "production_action": False,
                },
                indent=2,
            )
            + "\n"
        )
        assert failed == 0
    else:
        raise ValueError("Unknown probe")


if __name__ == "__main__":
    main()
