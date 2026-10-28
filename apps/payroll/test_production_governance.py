"""Production-scoped review qualified exclusively with synthetic TestCase data."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .source_package_services import (
    activate_statutory_source_package,
    import_statutory_source_package,
)
from .statutory_governance import validate_governance
from .test_cep069 import AdoptedStatutoryTests

ENVELOPES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/governance/production/PRODUCTION_STATUTORY_ENVELOPES.json"
    ).read_text("utf-8")
)


@override_settings(DEBUG=False, SETTINGS_MODULE="config.settings.production")
class ProductionEnvelopeTests(SimpleTestCase):
    def test_four_approved_versions_and_traceable_authority(self):
        for row in ENVELOPES:
            validate_governance(row["parameters"], policy_code=row["policy_code"])

    def test_unapproved_values_sources_scope_and_population_fail_closed(self):
        for key, value in (
            ("population", "UNREVIEWED"),
            ("review_sha256", "0" * 64),
            ("scope", "PRODUCTION"),
            ("production_authorization", {"reference": "other", "sha256": "0" * 64}),
        ):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                parameters = deepcopy(ENVELOPES[0]["parameters"])
                parameters["statutory_governance"][key] = value
                validate_governance(parameters, policy_code=ENVELOPES[0]["policy_code"])
        for key in ("brackets", "component_mappings"):
            parameters = deepcopy(ENVELOPES[0]["parameters"])
            parameters[key] = []
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_governance(parameters, policy_code=ENVELOPES[0]["policy_code"])

    def test_debug_wrong_settings_and_nonproduction_envelope_rejected(self):
        for debug, module in (
            (True, "config.settings.production"),
            (False, "config.settings.development"),
        ):
            with (
                override_settings(DEBUG=debug, SETTINGS_MODULE=module),
                self.assertRaises(ValidationError),
            ):
                validate_governance(
                    ENVELOPES[0]["parameters"], policy_code=ENVELOPES[0]["policy_code"]
                )
        parameters = deepcopy(ENVELOPES[0]["parameters"])
        parameters["statutory_governance"].pop("production_authorization")
        parameters["statutory_governance"]["scope"] = "NON_PRODUCTION_QUALIFICATION"
        with self.assertRaises(ValidationError):
            validate_governance(parameters, policy_code=ENVELOPES[0]["policy_code"])


@override_settings(DEBUG=False, SETTINGS_MODULE="config.settings.production")
class ProductionStatutoryTests(AdoptedStatutoryTests):
    # Execute the selected Production methods, using existing tenant/actor fixtures.
    def test_production_tax_and_insurance_import_activate_and_calculate(self):
        from .statutory_services import calculate_statutory

        self.context()
        for insurance, code, kind, expected in (
            (False, "payroll-tax-regulatory", "payroll_tax", "1000100"),
            (True, "employee-insurance-regulatory", "employee_insurance", "11637885"),
        ):
            row = next(row for row in ENVELOPES if row["policy_code"] == code)
            with patch(
                "apps.payroll.test_cep069.parameters",
                return_value=deepcopy(row["parameters"]),
            ):
                policy, payload = self.policy(insurance=insurance, accepted=True)
            package = import_statutory_source_package(
                actor=self.platform,
                policy_version=policy,
                payload=payload,
                reason="Approved Production scope, synthetic non-production qualification",
            )
            activate_statutory_source_package(
                actor=self.platform,
                package=package,
                reason="Synthetic qualification activation only",
            )
            result = calculate_statutory(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                kind=kind,
                reason="Production envelope synthetic calculation",
            )
            self.assertEqual(
                str(result.employee_amount.normalize()),
                str(__import__("decimal").Decimal(expected).normalize()),
            )
            snapshot = result.policy_snapshot
            self.assertEqual(snapshot["source_package_digest"], package.content_digest)
            self.assertEqual(
                package.content["policy"]["parameters"]["statutory_governance"][
                    "scope"
                ],
                "PRODUCTION_REVIEWED",
            )
            self.assertTrue(
                result.employee_results.get().calculation_snapshot["context"][
                    "evidence_digest"
                ]
            )
