"""Real-source PostgreSQL tests for the four SPEC-002 L2 adapter families."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.expenses import test_p4_s26_s30 as expense_fixtures
from apps.expenses.services import (
    approve_expense,
    create_expense_draft,
    submit_expense,
    void_expense,
)
from apps.fixed_assets.models import (
    AssetBookPolicyVersion,
    AssetTransaction,
    DepreciationLine,
    DepreciationRun,
    FixedAsset,
    FixedAssetClassVersion,
)
from apps.inventory.models import InventoryValuationEvent, Warehouse
from apps.inventory.services import create_stock_transaction, post_stock_transaction
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.payroll.models import (
    PayrollComponent,
    PayrollPeriod,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
)
from apps.projects.models import ProjectCostFact
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement
from apps.workforce.models import Employee

from .models import Account, FiscalPeriod, JournalEntry, JournalLine
from .recognition_models import SourceRecognitionDraft
from .recognition_services import (
    approve_recognition_mapping,
    attempt_source_recognition,
    prepare_recognition_mapping,
    prepare_source_recognition,
    reconcile_source_recognition,
)
from .services import create_fiscal_period, create_fiscal_year, submit_journal


class RecognitionFixture:
    _draft = expense_fixtures.ExpenseControlTests._draft
    _allocate = expense_fixtures.ExpenseControlTests._allocate

    def setUp(self):
        expense_fixtures.ExpenseControlTests.setUp(self)
        self.day = date(2026, 10, 1)
        permissions = [
            P.ACCOUNTING_RECOGNITION_MAPPINGS_MANAGE,
            P.ACCOUNTING_RECOGNITION_MAPPINGS_APPROVE,
            P.ACCOUNTING_RECOGNITION_PREPARE,
            P.ACCOUNTING_RECOGNITION_VIEW,
            P.PAYROLL_RESULTS_VIEW,
        ]
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="recognition-explicit",
            name="Explicit recognition",
            created_by=self.maker,
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=permissions))
        for actor in (self.maker, self.approver):
            membership = OrganizationMembership.objects.get(
                organization=self.organization, user=actor
            )
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=role,
                reason="Explicit test scope",
            )
        self.debit = Account.objects.create(
            organization=self.organization,
            code="42001",
            name="Explicit fixture debit",
            account_type="expense",
            is_posting=True,
            created_by=self.maker,
        )
        self.credit = Account.objects.create(
            organization=self.organization,
            code="22001",
            name="Explicit fixture credit",
            account_type="liability",
            is_posting=True,
            created_by=self.maker,
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.maker,
            code="CEP042",
            name="Year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.accounting_period = create_fiscal_period(
            organization=self.organization,
            actor=self.maker,
            fiscal_year=year,
            number=1,
            name="Period",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )

    def mapping(
        self, family, event, keys=("amount",), effective_from=None, approve=True
    ):
        mapping = prepare_recognition_mapping(
            organization=self.organization,
            actor=self.maker,
            source_family=family,
            source_event=event,
            effective_from=effective_from or self.day,
            account_assignments={
                key: {"debit": str(self.debit.pk), "credit": str(self.credit.pk)}
                for key in keys
            },
            evidence_reference="Explicit synthetic test mapping; no production value",
        )
        if approve:
            approve_recognition_mapping(
                organization=self.organization,
                actor=self.approver,
                mapping=mapping,
                reason="Independent synthetic acceptance",
            )
        return mapping

    def recognize(self, kind, source, **kwargs):
        return prepare_source_recognition(
            organization=self.organization,
            actor=self.maker,
            source_kind=kind,
            source_id=source.pk,
            **kwargs,
        )

    def reconcile(self, effect):
        result = reconcile_source_recognition(
            organization=self.organization, actor=self.maker, effect=effect
        )
        output = os.getenv("BONIRA_CEP042_INTEGRATION_TRACE")
        if output:
            path = Path(output)
            records = (
                json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            )
            records.append(
                {
                    **result,
                    "source_kind": effect.source_kind,
                    "source_event": effect.source_event,
                    "target_rows": effect.target_snapshot,
                    "native_source_metadata": effect.source_snapshot["metadata"],
                    "synthetic_test_data": True,
                }
            )
            path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        return result

    def expense(self, *, mapping=True):
        if mapping:
            self.mapping("Direct Expense", "approved")
        expense = self._draft()
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        approve_expense(expense=expense, actor=self.approver)
        expense.refresh_from_db()
        return expense

    def inventory(self, *, via_service=False):
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="TON",
            name="Ton",
            symbol="t",
            category="weight",
        )
        material = Material.objects.create(
            organization=self.organization,
            code="M42",
            name="Material",
            unit_of_measure=unit,
        )
        warehouse = Warehouse.objects.create(
            organization=self.organization, code="W42", name="Warehouse"
        )
        stock = create_stock_transaction(
            organization=self.organization,
            actor=self.maker,
            transaction_number="VAL42",
            transaction_type="adjustment_in",
            material=material,
            unit_of_measure=unit,
            quantity=1,
            destination_warehouse=warehouse,
            project=self.project,
            occurred_at=timezone.now(),
        )
        stock = post_stock_transaction(
            organization=self.organization, stock_transaction=stock, actor=self.maker
        )
        from apps.payroll import test_p7_s29_s32_financial_handoffs as payroll_fixtures

        self.owner = self.maker
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.maker
        )
        precision, rounding = (
            payroll_fixtures.PayrollFinancialHandoffTests._monetary_versions(self)
        )
        if via_service:
            from apps.inventory.p8_services import finalize_valuation

            return finalize_valuation(
                organization=self.organization,
                actor=self.maker,
                stock_transaction=stock,
                source_reference="VAL-SOURCE42",
                source_version="valuation-v4",
                unit_cost=Decimal(60),
                idempotency_key="value42",
            )
        return InventoryValuationEvent.objects.create(
            organization=self.organization,
            stock_transaction=stock,
            material=material,
            event_type="count_adjustment",
            quantity=1,
            unit_cost=60,
            value_amount=60,
            currency="IRR",
            source_reference="VAL-SOURCE42",
            source_version="valuation-v4",
            idempotency_key="value42",
            monetary_precision_version=precision,
            rounding_policy_version=rounding,
            finalized_by=self.maker,
            finalized_at=timezone.now(),
        )

    def payroll(self, *, original=None, replacement=False):
        employee = (
            original.employee_results.get().employee
            if original
            else Employee.objects.create(
                organization=self.organization,
                employee_number=f"E{PayrollRun.objects.count()}",
                first_name="Test",
                last_name="Person",
            )
        )
        period = (
            original.period
            if original
            else PayrollPeriod.objects.create(
                organization=self.organization,
                code=f"PAY{PayrollRun.objects.count()}",
                name="Payroll",
                starts_on=self.day,
                ends_on=self.day + timedelta(days=29),
                cutoff_at=timezone.now(),
                created_by=self.maker,
            )
        )
        run = PayrollRun.objects.create(
            organization=self.organization,
            period=period,
            code=f"RUN{PayrollRun.objects.count()}",
            kind="replacement"
            if replacement
            else "reversal"
            if original
            else "regular",
            status="finalized",
            idempotency_key=str(uuid4()),
            calculation_digest=str(uuid4()),
            created_by=self.maker,
            finalized_by=self.maker,
            finalized_at=timezone.now(),
            reversal_of=original if original and not replacement else None,
            replaces=original if replacement else None,
        )
        result = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=run,
            employee=employee,
            project=self.project,
            status="finalized",
            gross_amount=-60 if original and not replacement else 60,
            net_amount=-60 if original and not replacement else 60,
        )
        component = PayrollComponent.objects.first() or PayrollComponent.objects.create(
            organization=self.organization,
            code="C42",
            name="Explicit component",
            kind="earning",
            net_effect="add",
            created_by=self.maker,
        )
        line = PayrollResultLine.objects.create(
            organization=self.organization,
            run=run,
            run_employee=result,
            component=component,
            sequence=1,
            component_kind="earning",
            unrounded_amount=-60 if original and not replacement else 60,
            amount=-60 if original and not replacement else 60,
            explanation={"source": "explicit synthetic finalized fixture"},
        )
        return run, line

    def asset(self):
        asset_class = FixedAssetClassVersion.objects.create(
            organization=self.organization,
            code="CLASS42",
            name="Asset class",
            version=3,
            status="published",
            effective_from=self.day,
            account_mapping_reference="Explicit map reference",
            capitalization_policy_reference="Explicit capitalization reference",
            prepared_by=self.maker,
        )
        book = AssetBookPolicyVersion.objects.create(
            organization=self.organization,
            code="BOOK42",
            version=2,
            status="published",
            effective_from=self.day,
            monetary_policy_code="accounting-money-precision",
            monetary_policy_version="v1",
            convention="full_month",
            prepared_by=self.maker,
        )
        asset = FixedAsset.objects.create(
            organization=self.organization,
            asset_number="FA42",
            name="Asset",
            asset_class=asset_class,
            book_policy=book,
            ready_for_use_date=self.day,
            useful_life_months=12,
            residual_value=0,
            capitalization_basis=60,
            project=self.project,
            evidence_reference="Explicit source",
            prepared_by=self.maker,
        )
        tx = AssetTransaction.objects.create(
            organization=self.organization,
            asset=asset,
            transaction_type="capitalization",
            status="finalized",
            occurred_on=self.day,
            amount=60,
            occurrence_key="CAP42",
            reason="Source backed",
            source_dimensions_captured=True,
            source_project=self.project,
            prepared_by=self.maker,
            reviewed_by=self.approver,
            finalized_at=timezone.now(),
        )
        return asset, tx


class RecognitionSourceTests(RecognitionFixture, TestCase):
    def test_expense_source_hook_creates_one_mapped_draft_and_preserves_authorities(
        self,
    ):
        before = (
            Obligation.objects.count(),
            TreasuryMovement.objects.count(),
            ProjectCostFact.objects.count(),
        )
        source = self.expense()
        effect = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        self.assertEqual(self.recognize("expense", source).pk, effect.pk)
        self.assertEqual(effect.journal.status, "draft")
        self.assertEqual(effect.journal.lines.count(), 2)
        self.assertEqual(self.reconcile(effect)["status"], "matched")
        self.assertEqual(
            before,
            (
                Obligation.objects.count(),
                TreasuryMovement.objects.count(),
                ProjectCostFact.objects.count(),
            ),
        )
        with self.assertRaises(ValidationError):
            submit_journal(
                organization=self.organization,
                actor=self.approver,
                journal=effect.journal,
            )

    def test_expense_void_and_replacement_have_retained_reversal_lineage(self):
        source = self.expense()
        original = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        void_expense(expense=source, actor=self.approver, reason="Correction")
        reverse = SourceRecognitionDraft.objects.get(
            source_uuid=source.pk, is_reversal=True
        )
        self.assertEqual(reverse.predecessor_id, original.pk)
        self.assertEqual(
            reverse.journal.lines.get(line_number=1).credit,
            original.journal.lines.get(line_number=1).debit,
        )
        replacement = create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            description="Replacement",
            amount=Decimal(70),
            incurred_on=self.day,
            source_reference="NEW42",
            idempotency_key="replacement42",
            replaces=source,
        )
        self._allocate(replacement)
        submit_expense(expense=replacement, actor=self.maker)
        approve_expense(expense=replacement, actor=self.approver)
        effect = SourceRecognitionDraft.objects.get(source_uuid=replacement.pk)
        self.assertEqual(effect.predecessor_id, original.pk)
        self.assertEqual(self.reconcile(original)["status"], "matched")
        self.assertEqual(self.reconcile(reverse)["status"], "matched")
        self.assertEqual(self.reconcile(effect)["status"], "matched")

    def test_inventory_native_version_and_no_mapping_fallback(self):
        self.mapping("Inventory", "count_adjustment:adjustment_in")
        source = self.inventory(via_service=True)
        self.assertEqual(
            SourceRecognitionDraft.objects.filter(source_uuid=source.pk).count(), 1
        )
        effect = self.recognize("inventory", source)
        self.assertEqual(effect.source_version_reference, "valuation-v4")
        self.assertEqual(
            effect.source_snapshot["metadata"]["stock_id"],
            str(source.stock_transaction_id),
        )
        self.assertEqual(self.recognize("inventory", source).pk, effect.pk)
        self.assertEqual(self.reconcile(effect)["status"], "matched")

    def test_payroll_source_components_reversal_and_replacement(self):
        run, line = self.payroll()
        mapping = self.mapping(
            "Payroll", "finalized", (f"component:{line.component_id}",)
        )
        original = self.recognize("payroll", run)
        self.assertEqual(original.mapping_id, mapping.pk)
        reverse, _ = self.payroll(original=run)
        reversal = self.recognize("payroll", reverse)
        replacement, _ = self.payroll(original=run, replacement=True)
        effect = self.recognize("payroll", replacement)
        self.assertEqual(reversal.predecessor_id, original.pk)
        self.assertEqual(effect.predecessor_id, original.pk)
        self.assertTrue(reversal.is_reversal)
        self.assertEqual(self.reconcile(reversal)["status"], "matched")
        self.assertEqual(self.reconcile(effect)["status"], "matched")
        self.assertEqual(self.recognize("payroll", run).pk, original.pk)

    def test_asset_and_depreciation_pin_book_and_explicit_mapping(self):
        asset, tx = self.asset()
        self.mapping("Fixed Assets", "capitalization")
        original = self.recognize("asset", tx)
        self.assertIn("class:3;book:2", original.source_version_reference)
        self.mapping("Fixed Assets", "depreciation", (f"class:{asset.asset_class_id}",))
        run = DepreciationRun.objects.create(
            organization=self.organization,
            book_policy=asset.book_policy,
            fiscal_period=self.accounting_period,
            status="finalized",
            occurrence_key="DEP42",
            source_watermark=timezone.now(),
            prepared_by=self.maker,
            finalized_by=self.approver,
            finalized_at=timezone.now(),
        )
        DepreciationLine.objects.create(
            organization=self.organization,
            run=run,
            asset=asset,
            basis_snapshot=60,
            residual_snapshot=0,
            useful_life_months_snapshot=12,
            prior_accumulated_depreciation=0,
            depreciation_amount=5,
            carrying_value_after=55,
            convention_snapshot="full_month",
        )
        effect = self.recognize("depreciation", run)
        self.assertEqual(self.reconcile(effect)["status"], "matched")
        self.assertEqual(self.recognize("depreciation", run).pk, effect.pk)
        from apps.fixed_assets.services import reverse_depreciation

        reversal_run = reverse_depreciation(
            organization=self.organization,
            actor=self.maker,
            run=run,
            occurrence_key="DEP-REV42",
            reason="Explicit source correction",
        )
        reversal = SourceRecognitionDraft.objects.get(source_uuid=reversal_run.pk)
        self.assertEqual(reversal.predecessor_id, effect.pk)
        self.assertEqual(self.reconcile(reversal)["status"], "matched")
        self.assertEqual(self.reconcile(effect)["status"], "matched")

    def test_failure_rolls_back_target_retains_approved_source_and_retry_evidence(self):
        self.mapping("Direct Expense", "approved")
        with patch(
            "apps.accounting.recognition_services.JournalLine.objects.create",
            side_effect=DatabaseError("injected"),
        ):
            source = self.expense(mapping=False)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

        self.assertEqual(source.status, "approved")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_SOURCE_RECOGNITION_FAILED,
                entity_id=str(source.pk),
            ).exists()
        )
        self.assertIsNotNone(
            attempt_source_recognition(
                organization=self.organization,
                actor=self.approver,
                source_kind="expense",
                source_id=source.pk,
            )
        )

    def test_inventory_reversal_is_inverse_of_original_pinned_mapping(self):
        from apps.inventory.p8_services import reverse_valuation
        from apps.inventory.services import reverse_stock_transaction

        self.mapping("Inventory", "count_adjustment:adjustment_in")
        source = self.inventory(via_service=True)
        original = self.recognize("inventory", source)
        stock = reverse_stock_transaction(
            organization=self.organization,
            actor=self.approver,
            stock_transaction=source.stock_transaction,
            reversal_number="REV42",
            reason="Explicit reversal",
        )
        reversal_source = reverse_valuation(
            organization=self.organization,
            actor=self.approver,
            stock_transaction=stock,
            idempotency_key="value-reverse42",
        )
        reversal = SourceRecognitionDraft.objects.get(source_uuid=reversal_source.pk)
        self.assertTrue(reversal.is_reversal)
        self.assertEqual(reversal.mapping_id, original.mapping_id)
        self.assertEqual(self.reconcile(reversal)["status"], "matched")
        self.assertEqual(self.reconcile(original)["status"], "matched")

    def test_asset_reversal_source_hook_preserves_original_and_retries(self):
        from apps.fixed_assets.services import reverse_asset_transaction

        _asset, tx = self.asset()
        self.mapping("Fixed Assets", "capitalization")
        original = self.recognize("asset", tx)
        reversal_tx = reverse_asset_transaction(
            organization=self.organization,
            actor=self.maker,
            transaction_record=tx,
            occurrence_key="FA-REV42",
            reason="Explicit reversal",
        )
        reversal = SourceRecognitionDraft.objects.get(source_uuid=reversal_tx.pk)
        self.assertEqual(reversal.predecessor_id, original.pk)
        self.assertEqual(self.recognize("asset", reversal_tx).pk, reversal.pk)
        self.assertEqual(self.reconcile(original)["status"], "matched")
        self.assertEqual(self.reconcile(reversal)["status"], "matched")

    def test_inactive_historical_account_cannot_rollback_asset_reversal_authority(self):
        from apps.fixed_assets.services import reverse_asset_transaction

        _asset, tx = self.asset()
        self.mapping("Fixed Assets", "capitalization")
        original = self.recognize("asset", tx)
        Account.objects.filter(pk=self.debit.pk).update(
            is_posting=False, archived_at=timezone.now()
        )
        reversal_tx = reverse_asset_transaction(
            organization=self.organization,
            actor=self.maker,
            transaction_record=tx,
            occurrence_key="ARCHIVED-REV42",
            reason="Explicit source reversal",
        )
        reversal_tx.refresh_from_db()
        self.assertEqual(reversal_tx.status, "finalized")
        self.assertFalse(
            SourceRecognitionDraft.objects.filter(source_uuid=reversal_tx.pk).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_SOURCE_RECOGNITION_FAILED,
                entity_id=str(reversal_tx.pk),
            ).exists()
        )
        self.assertEqual(self.reconcile(original)["status"], "matched")

    def test_missing_and_unapproved_mapping_preserve_source_and_no_effect(self):
        source = self.expense(mapping=False)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 0)
        with self.assertRaises(ValidationError):
            self.recognize("expense", source)
        mapping = self.mapping("Direct Expense", "approved", approve=False)
        with self.assertRaises(ValidationError):
            self.recognize("expense", source)
        with self.assertRaises(ValidationError):
            approve_recognition_mapping(
                organization=self.organization,
                actor=self.maker,
                mapping=mapping,
                reason="Own mapping",
            )

    def test_immutable_mapping_effect_and_no_implicit_default_grants(self):
        source = self.expense()
        effect = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        for obj in (effect, effect.mapping, effect.mapping.approval):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).delete()
        for permissions in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertNotIn(P.ACCOUNTING_RECOGNITION_VIEW, permissions)
            self.assertNotIn(P.ACCOUNTING_RECOGNITION_PREPARE, permissions)

    def test_replay_pins_old_mapping_new_mapping_is_prospective_only(self):
        source = self.expense()
        effect = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        later = self.mapping(
            "Direct Expense", "approved", effective_from=date(2026, 10, 2)
        )
        self.assertNotEqual(effect.mapping_id, later.pk)
        self.assertEqual(
            self.recognize("expense", source).mapping_id, effect.mapping_id
        )

    def test_reconciliation_detects_target_drift_and_retry_does_not_duplicate(self):
        source = self.expense()
        effect = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        JournalLine.objects.filter(journal=effect.journal, line_number=1).update(
            debit=61
        )
        self.assertEqual(self.reconcile(effect)["status"], "exception")
        with self.assertRaises(ValidationError):
            self.recognize("expense", source)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 1)

    def test_replay_rejects_draft_header_tampering_and_closed_period(self):
        source = self.expense()
        effect = SourceRecognitionDraft.objects.get(source_uuid=source.pk)
        JournalEntry.objects.filter(pk=effect.journal_id).update(
            description="Changed header"
        )
        self.assertEqual(self.reconcile(effect)["status"], "exception")
        with self.assertRaises(ValidationError):
            self.recognize("expense", source)
        # Arrange an already-closed authoritative period; do not invoke closeout
        # while this fixture deliberately contains an unresolved draft.
        FiscalPeriod.objects.filter(pk=self.accounting_period.pk).update(
            status="closed"
        )
        new_source = self._draft(key="closed42", source="closed42")
        self._allocate(new_source)
        submit_expense(expense=new_source, actor=self.maker)
        approve_expense(expense=new_source, actor=self.approver)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 1)

    def test_unknown_asset_treatment_and_cross_tenant_mapping_have_no_fallback(self):
        _asset, tx = self.asset()
        with self.assertRaises(ValidationError):
            self.mapping("Fixed Assets", "impairment")
        mapping = self.mapping("Fixed Assets", "capitalization", approve=False)
        mapping.account_assignments = {
            "amount": {"debit": str(uuid4()), "credit": str(self.credit.pk)}
        }
        with self.assertRaises(ValidationError):
            mapping.clean()
        with self.assertRaises(ValidationError):
            self.recognize("asset", tx)

    def test_unfinalized_unclassified_unknown_and_cross_tenant_sources_fail_closed(
        self,
    ):
        source = self._draft()
        for kind, identity in [
            ("expense", source.pk),
            ("Payroll payable/disbursement request", uuid4()),
            ("expense", uuid4()),
        ]:
            with (
                self.subTest(kind=kind),
                self.assertRaises((ValidationError, PermissionDenied)),
            ):
                prepare_source_recognition(
                    organization=self.organization,
                    actor=self.maker,
                    source_kind=kind,
                    source_id=identity,
                )
        with self.assertRaises(PermissionDenied):
            prepare_source_recognition(
                organization=self.organization,
                actor=self.outsider,
                source_kind="expense",
                source_id=source.pk,
            )
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_target_failure_and_retry_preserve_each_recognition_source_family(self):
        expense = self.expense(mapping=False)
        inventory = self.inventory()
        payroll, line = self.payroll()
        _asset, asset = self.asset()
        for family, event, keys in [
            ("Direct Expense", "approved", ("amount",)),
            ("Inventory", "count_adjustment:adjustment_in", ("amount",)),
            ("Payroll", "finalized", (f"component:{line.component_id}",)),
            ("Fixed Assets", "capitalization", ("amount",)),
        ]:
            self.mapping(family, event, keys)
        for index, (kind, source) in enumerate(
            (
                ("expense", expense),
                ("inventory", inventory),
                ("payroll", payroll),
                ("asset", asset),
            )
        ):
            with self.subTest(kind=kind):
                with patch(
                    "apps.accounting.recognition_services.JournalLine.objects.create",
                    side_effect=DatabaseError("injected target failure"),
                ):
                    self.assertIsNone(
                        attempt_source_recognition(
                            organization=self.organization,
                            actor=self.maker,
                            source_kind=kind,
                            source_id=source.pk,
                        )
                    )
                self.assertEqual(SourceRecognitionDraft.objects.count(), index)
                self.assertEqual(JournalEntry.objects.count(), index)
                effect = self.recognize(kind, source)
                self.assertEqual(self.reconcile(effect)["status"], "matched")
                self.assertEqual(self.recognize(kind, source).pk, effect.pk)

    def test_missing_payroll_component_mapping_never_uses_another_component(self):
        run, _line = self.payroll()
        other = PayrollComponent.objects.create(
            organization=self.organization,
            code="OTHER42",
            name="Other",
            kind="earning",
            net_effect="add",
            created_by=self.maker,
        )
        self.mapping("Payroll", "finalized", (f"component:{other.pk}",))
        with self.assertRaises(ValidationError):
            self.recognize("payroll", run)
        self.assertEqual(JournalEntry.objects.count(), 0)


class RecognitionConcurrencyTests(RecognitionFixture, TransactionTestCase):
    def test_concurrent_retry_of_same_finalized_source_creates_one_target(self):
        source = self.expense(mapping=False)
        self.mapping("Direct Expense", "approved")
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return str(
                    prepare_source_recognition(
                        organization=self.organization,
                        actor=self.maker,
                        source_kind="expense",
                        source_id=source.pk,
                    ).pk
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run) for _ in range(2)]
            result = [future.result(timeout=30) for future in futures]
        self.assertEqual(result[0], result[1])
        self.assertEqual(SourceRecognitionDraft.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_SOURCE_RECOGNIZED
            ).count(),
            1,
        )
