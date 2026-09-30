from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounting.models import (
    FinancialStatementKind,
    FinancialStatementRun,
    FiscalPeriodControlEvent,
    FiscalPeriodStatus,
    JournalKind,
    JournalStatus,
)
from apps.accounting.reconciliation import (
    create_manual_opening_reconciliation_run,
    inspect_manual_opening_reconciliation,
    sign_off_reconciliation_run,
)
from apps.accounting.reporting import build_statement, retain_statement
from apps.accounting.services import (
    add_journal_line,
    close_period,
    create_controlled_adjustment,
    create_fiscal_period,
    create_journal,
    post_journal,
    reopen_period,
    submit_journal,
)
from apps.organizations.models import MembershipRole, OrganizationMembership


def _foundation():
    from apps.accounting.tests import AccountingFoundationTests

    return AccountingFoundationTests


class AccountingStatementsCloseAdjustmentTests(TestCase):
    """Focused PostgreSQL acceptance for the bounded P2-S28--S34 contract."""

    def setUp(self) -> None:
        _foundation().setUp(self)

    def _member(self, *args, **kwargs):
        return _foundation()._member(self, *args, **kwargs)

    def _journal(self):
        return _foundation()._journal(self)

    def _activate_accounting_policy(self, *args, **kwargs):
        return _foundation()._activate_accounting_policy(self, *args, **kwargs)

    def _activate_posting_policies(self):
        return _foundation()._activate_posting_policies(self)

    def _posted_journal(self):
        return _foundation()._posted_journal(self)

    def _activate_client(self, user, organization=None, *, csrf=False) -> Client:
        client = Client(enforce_csrf_checks=csrf)
        client.force_login(user)
        session = client.session
        session["active_organization_id"] = str((organization or self.organization).pk)
        session.save()
        return client

    def _signed_reconciliation(self):
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=self.period.ends_on,
        )
        sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="independent close reconciliation",
        )
        return run

    def _close_period(self):
        self._signed_reconciliation()
        return close_period(
            organization=self.organization,
            actor=self.approver,
            period=self.period,
            requested_by=self.owner_membership,
            reason="period checklist completed",
        )

    def test_trial_balance_uses_only_posted_lines_and_is_tenant_scoped(self) -> None:
        self._posted_journal()
        draft = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 10),
            accounting_date=date(2026, 1, 10),
            description="draft is not ledger evidence",
            source_key="DRAFT-NOT-LEDGER",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=draft,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(900),
        )
        report = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.TRIAL_BALANCE,
            starts_on=self.period.starts_on,
            ends_on=self.period.ends_on,
        )
        self.assertEqual(report.source_line_count, 2)
        self.assertEqual(report.debit_total, Decimal(100))
        self.assertEqual(report.credit_total, Decimal(100))
        self.assertNotIn(Decimal(900), [line.period_debit for line in report.lines])

        viewer = self._member("p2-report-viewer", MembershipRole.VIEWER)
        with self.assertRaises(PermissionDenied):
            build_statement(
                organization=self.organization,
                actor=viewer,
                kind=FinancialStatementKind.TRIAL_BALANCE,
                ends_on=self.period.ends_on,
            )
        with self.assertRaises(PermissionDenied):
            build_statement(
                organization=self.other_organization,
                actor=self.owner,
                kind=FinancialStatementKind.TRIAL_BALANCE,
                ends_on=self.period.ends_on,
            )

    def test_retained_statement_is_immutable_and_cutoff_stable(self) -> None:
        self._posted_journal()
        retained = retain_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.TRIAL_BALANCE,
            starts_on=self.period.starts_on,
            ends_on=self.period.ends_on,
        )
        original_hash = retained.result_hash
        original_lines = list(retained.lines.values_list("amount", flat=True))

        next_period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            number=2,
            name="دوره دوم",
            starts_on=date(2026, 2, 1),
            ends_on=date(2026, 2, 28),
        )
        later = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=next_period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 2, 2),
            accounting_date=date(2026, 2, 2),
            description="later fact",
            source_key="LATER-FACT",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=later,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(40),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=later,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(40),
        )
        later = submit_journal(
            organization=self.organization, actor=self.owner, journal=later
        )
        post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=later,
            reason="later independent post",
        )
        retained.refresh_from_db()
        self.assertEqual(retained.result_hash, original_hash)
        self.assertEqual(
            list(retained.lines.values_list("amount", flat=True)), original_lines
        )
        with self.assertRaises(ValidationError):
            retained.result_hash = "0" * 64
            retained.save()
        line = retained.lines.first()
        with self.assertRaises(ValidationError):
            line.amount = Decimal(0)
            line.save()

    def test_balance_sheet_and_profit_loss_are_accurate(self) -> None:
        self._posted_journal()
        expense = self.debit_account.__class__.objects.create(
            organization=self.organization,
            code="5100",
            name="هزینه دوره",
            account_type="expense",
            is_posting=True,
            created_by=self.owner,
        )
        manual = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 20),
            accounting_date=date(2026, 1, 20),
            description="period expense",
            source_key="PERIOD-EXPENSE",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=manual,
            account=expense,
            line_number=1,
            debit=Decimal(20),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=manual,
            account=self.debit_account,
            line_number=2,
            credit=Decimal(20),
        )
        manual = submit_journal(
            organization=self.organization, actor=self.owner, journal=manual
        )
        post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=manual,
            reason="expense reviewed",
        )
        profit_loss = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.PROFIT_LOSS,
            starts_on=self.period.starts_on,
            ends_on=self.period.ends_on,
        )
        balance_sheet = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.BALANCE_SHEET,
            ends_on=self.period.ends_on,
        )
        self.assertEqual(profit_loss.net_total, Decimal(-20))
        self.assertEqual(balance_sheet.net_total, Decimal(-20))
        asset = next(
            line for line in balance_sheet.lines if line.account_code == "1100"
        )
        self.assertEqual(asset.amount, Decimal(80))

    def test_close_requires_signed_reconciliation_and_retains_evidence(self) -> None:
        self._posted_journal()
        with self.assertRaises(ValidationError):
            close_period(
                organization=self.organization,
                actor=self.approver,
                period=self.period,
                requested_by=self.owner_membership,
                reason="missing checklist",
            )
        self._close_period()
        self.period.refresh_from_db()
        event = FiscalPeriodControlEvent.objects.get(period=self.period, action="close")
        self.assertEqual(self.period.status, FiscalPeriodStatus.CLOSED)
        self.assertIsNotNone(event.reconciliation_run_id)
        self.assertIsNotNone(event.trial_balance_run_id)
        self.assertIsNotNone(event.balance_sheet_run_id)
        self.assertIsNotNone(event.profit_loss_run_id)
        self.assertEqual(len(event.evidence_hash), 64)
        with self.assertRaises(ValidationError):
            event.reason = "rewrite"
            event.save()

    def test_reopen_is_separated_and_preserves_prior_close(self) -> None:
        self._posted_journal()
        self._close_period()
        approver_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.approver
        )
        with self.assertRaises(PermissionDenied):
            reopen_period(
                organization=self.organization,
                actor=self.approver,
                period=self.period,
                requested_by=approver_membership,
                reason="same actor",
            )
        second_owner = self._member("p2-second-owner", MembershipRole.TENANT_OWNER)
        reopened = reopen_period(
            organization=self.organization,
            actor=second_owner,
            period=self.period,
            requested_by=self.owner_membership,
            reason="independent reopen after review",
        )
        self.assertEqual(reopened.status, FiscalPeriodStatus.OPEN)
        events = list(self.period.control_events.order_by("sequence"))
        self.assertEqual([event.action for event in events], ["close", "reopen"])
        self.assertEqual(events[1].related_close_id, events[0].pk)
        self.assertEqual(FinancialStatementRun.objects.count(), 3)

    def test_controlled_adjustment_preserves_closed_journal_lineage(self) -> None:
        original = self._posted_journal()
        self._close_period()
        adjustment_period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            number=13,
            name="دوره تعدیلی",
            starts_on=date(2026, 12, 31),
            ends_on=date(2026, 12, 31),
            is_adjustment=True,
        )
        adjustment = create_controlled_adjustment(
            organization=self.organization,
            actor=self.owner,
            original=original,
            period=adjustment_period,
            document_date=date(2026, 12, 31),
            accounting_date=date(2026, 12, 31),
            description="late classified adjustment",
            source_key="ADJ-2026-001",
            reason="approved late correction",
            evidence_reference="evidence://adjustment/1",
            reconciliation_reference="reconciliation://adjustment/1",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=adjustment,
            account=self.debit_account,
            line_number=1,
            debit=Decimal(10),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=adjustment,
            account=self.credit_account,
            line_number=2,
            credit=Decimal(10),
        )
        adjustment = submit_journal(
            organization=self.organization, actor=self.owner, journal=adjustment
        )
        adjustment = post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=adjustment,
            reason="independent adjustment approval",
        )
        original.refresh_from_db()
        self.assertEqual(adjustment.adjusts_id, original.pk)
        self.assertEqual(adjustment.kind, JournalKind.MANUAL)
        self.assertEqual(original.status, JournalStatus.POSTED)
        self.assertEqual(original.lines.count(), 2)
        reconciliation = inspect_manual_opening_reconciliation(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=adjustment_period.ends_on,
        )
        adjustment_tie_out = next(
            tie_out
            for tie_out in reconciliation.tie_outs
            if tie_out.journal_uuid == adjustment.pk
        )
        self.assertTrue(adjustment_tie_out.correction_chain_matches)
        self.assertEqual(
            adjustment_tie_out.evidence["adjusts_journal_uuid"], str(original.pk)
        )
        with self.assertRaises(ValidationError):
            adjustment.adjustment_reason = "rewrite"
            adjustment.save()

    def test_reporting_ui_is_tenant_scoped_permissioned_and_csrf_protected(
        self,
    ) -> None:
        self._posted_journal()
        run = retain_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.TRIAL_BALANCE,
            ends_on=self.period.ends_on,
        )
        owner_client = self._activate_client(self.owner)
        response = owner_client.get(reverse("accounting:statement_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فقط بر پایه ردیف‌های قطعی")
        self.assertEqual(
            owner_client.get(
                reverse("accounting:statement_detail", args=[run.pk])
            ).status_code,
            200,
        )
        other_client = self._activate_client(self.other_owner, self.other_organization)
        self.assertEqual(
            other_client.get(
                reverse("accounting:statement_detail", args=[run.pk])
            ).status_code,
            404,
        )
        viewer = self._member("p2-ui-report-viewer", MembershipRole.VIEWER)
        viewer_client = self._activate_client(viewer)
        self.assertEqual(
            viewer_client.get(reverse("accounting:statement_list")).status_code,
            403,
        )
        csrf_client = self._activate_client(self.owner, csrf=True)
        self.assertEqual(
            csrf_client.post(
                reverse("accounting:statement_run"),
                {
                    "kind": FinancialStatementKind.TRIAL_BALANCE,
                    "ends_on": "2026-01-31",
                },
            ).status_code,
            403,
        )
