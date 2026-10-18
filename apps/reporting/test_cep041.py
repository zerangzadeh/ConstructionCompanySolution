from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.audit.models import AuditEvent

from . import test_p10_s07_s13 as baseline
from .models import ReconciliationOutcome
from .reconciliation import PairData, SideData, _compare


def comparison(left="10.00", right="9.99"):
    return PairData(
        SideData("Source", "source.Left", "ready", {"amount": left}, {"ids": ["1"]}),
        SideData("Source", "source.Right", "ready", {"amount": right}, {"ids": ["2"]}),
        "amount",
    )


class ToleranceBoundaryTests(SimpleTestCase):
    def test_missing_source_native_and_unknown_policies_never_auto_accept(self):
        for rule in (
            None,
            {},
            {"absolute": "100"},
            {"kind": "source_policy", "absolute": "100"},
            {"kind": "native_policy", "absolute": "100"},
            {"kind": "unregistered", "absolute": "100"},
        ):
            with self.subTest(rule=rule):
                outcome, diff, tolerance, materiality = _compare(
                    comparison(), {"tolerance": rule}
                )
                self.assertEqual(outcome, ReconciliationOutcome.MISMATCH)
                self.assertEqual(Decimal(diff["amount"]), Decimal("0.01"))
                self.assertFalse(tolerance["applied"])
                self.assertIsNone(tolerance["absolute"])
                self.assertEqual(tolerance["status"], "unconfigured")
                self.assertEqual(
                    materiality["reason"], "approved_source_tolerance_absent"
                )

    def test_equality_does_not_claim_an_unconfigured_tolerance(self):
        result = _compare(comparison(right="10.00"), {"tolerance": {}})
        self.assertEqual(result[0], ReconciliationOutcome.MATCHED_EXACT)
        self.assertFalse(result[2]["applied"])

    def test_exact_catalogue_rule_is_deterministic_and_input_is_unchanged(self):
        spec = {"tolerance": {"kind": "exact", "absolute": "0"}}
        before = deepcopy(spec)
        first = _compare(comparison(), spec)
        self.assertEqual(first, _compare(comparison(), spec))
        self.assertEqual(first[0], ReconciliationOutcome.MISMATCH)
        self.assertEqual(first[2]["absolute"], "0")
        self.assertTrue(first[2]["applied"])
        self.assertEqual(spec, before)

    def test_invalid_exact_rules_cannot_become_thresholds(self):
        for value in (None, "", "bad", "NaN", "Infinity", "-1", "0.01"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                _compare(
                    comparison(), {"tolerance": {"kind": "exact", "absolute": value}}
                )

    def test_source_basis_points_are_not_an_aggregate_money_tolerance(self):
        data = comparison()
        data.left.manifest["quantity_tolerance_bps"] = 10000
        data.right.manifest["unit_price_tolerance_bps"] = 10000
        result = _compare(data, {"tolerance": {"kind": "source_policy"}})
        self.assertEqual(result[0], ReconciliationOutcome.MISMATCH)
        self.assertFalse(result[2]["applied"])


class PersistedToleranceTests(baseline.P10S07S13AcceptanceTests):
    # Inherited cases are the affected 25-test regression, run once in this module.
    def test_policy_absence_is_retained_in_tieout_exception_and_audit(self):
        with patch.dict(
            "apps.reporting.reconciliation.ADAPTERS",
            {"po_receipt_invoice": lambda *args: comparison()},
        ):
            run = self._run(code="po_receipt_invoice", key="policy-absent")
        tie = run.tie_out
        self.assertEqual(tie.outcome, ReconciliationOutcome.MISMATCH)
        self.assertEqual(tie.difference["amount"], "0.01")
        evidence = tie.tolerance_result
        self.assertEqual(evidence["pair_version_id"], str(run.pair_version_id))
        self.assertEqual(len(evidence["specification_hash"]), 64)
        self.assertEqual(evidence["source_models"], ["source.Left", "source.Right"])
        self.assertFalse(evidence["applied"])
        exception = run.exceptions.get()
        self.assertEqual(exception.classification, "approved_source_tolerance_absent")
        event = AuditEvent.objects.get(entity_id=str(run.pk))
        self.assertEqual(event.metadata["tolerance"], evidence)
        tie.tolerance_result = {"applied": True}
        with self.assertRaises(ValidationError):
            tie.save()

    def test_new_run_keeps_prior_comparison_and_source_identity(self):
        with patch.dict(
            "apps.reporting.reconciliation.ADAPTERS",
            {"po_receipt_invoice": lambda *args: comparison()},
        ):
            first = self._run(code="po_receipt_invoice", key="prior-policy")
        retained = deepcopy(first.tie_out.tolerance_result)
        retained_hash = first.tie_out.calculation_hash
        with patch.dict(
            "apps.reporting.reconciliation.ADAPTERS",
            {"po_receipt_invoice": lambda *args: comparison(right="10.00")},
        ):
            second = self._run(code="po_receipt_invoice", key="next-policy")
        first.tie_out.refresh_from_db()
        self.assertEqual(first.tie_out.tolerance_result, retained)
        self.assertEqual(first.tie_out.calculation_hash, retained_hash)
        self.assertEqual(first.tie_out.outcome, ReconciliationOutcome.MISMATCH)
        self.assertEqual(second.tie_out.outcome, ReconciliationOutcome.MATCHED_EXACT)
        self.assertFalse(second.tie_out.tolerance_result["applied"])
