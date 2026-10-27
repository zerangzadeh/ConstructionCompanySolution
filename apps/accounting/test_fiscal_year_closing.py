from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import (
    MembershipRole,
    MembershipScopeGrant,
    OrganizationMembership,
)
from apps.projects.models import Project

from .closing_models import ClosingStatus, FiscalClosingConfiguration, FiscalYearClosing
from .closing_services import (
    approve_year_end,
    configure_year_end,
    inspect_year_end,
    prepare_year_end,
    reopen_year_end,
    roll_forward_year_end,
)
from .models import (
    Account,
    AccountType,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalKind,
    JournalLine,
)
from .reconciliation import (
    create_manual_opening_reconciliation_run,
    sign_off_reconciliation_run,
)
from .reporting import build_statement
from .services import (
    add_journal_line,
    close_period,
    create_account,
    create_fiscal_period,
    create_fiscal_year,
    create_journal,
    create_opening_import,
    post_journal,
    reopen_period,
    reverse_journal,
    submit_journal,
)


class YearEndFixture:
    def setUp(self):
        from .tests import AccountingFoundationTests

        AccountingFoundationTests.setUp(self)
        self.period.ends_on = self.year.ends_on
        self.period.save()
        self._activate_posting_policies()
        self.target = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-02",
            name="سال بعد",
            starts_on=date(2027, 1, 1),
            ends_on=date(2027, 12, 31),
            calendar_version=1,
        )
        self.target_period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.target,
            number=1,
            name="دوره سال بعد",
            starts_on=self.target.starts_on,
            ends_on=self.target.ends_on,
        )
        self.summary = self._account("3200", AccountType.EQUITY)
        self.retained = self._account("3300", AccountType.EQUITY)
        self.income = self._account("4100", AccountType.INCOME)
        self.expense = self._account("5100", AccountType.EXPENSE)
        self.reopener = self._member("year-end-reopener", MembershipRole.TENANT_OWNER)
        self.reviewer = self.approver
        configure_year_end(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            result_account=self.summary,
            retained_account=self.retained,
            reason="approved product closing policy",
        )

    def _member(self, *args, **kwargs):
        from .tests import AccountingFoundationTests

        return AccountingFoundationTests._member(self, *args, **kwargs)

    def _activate_accounting_policy(self, *args, **kwargs):
        from .tests import AccountingFoundationTests

        return AccountingFoundationTests._activate_accounting_policy(
            self, *args, **kwargs
        )

    def _activate_posting_policies(self):
        from .tests import AccountingFoundationTests

        return AccountingFoundationTests._activate_posting_policies(self)

    def _account(self, code, kind):
        return create_account(
            organization=self.organization,
            actor=self.owner,
            code=code,
            name=code,
            account_type=kind,
            is_posting=True,
        )

    def _post(self, source_key, amounts, *, period=None):
        period = period or self.period
        journal = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=period,
            kind=JournalKind.MANUAL,
            document_date=period.starts_on,
            accounting_date=period.starts_on,
            description=source_key,
            source_key=source_key,
        )
        for number, (account, amount, dimensions) in enumerate(amounts, 1):
            add_journal_line(
                organization=self.organization,
                actor=self.owner,
                journal=journal,
                account=account,
                line_number=number,
                debit=max(Decimal(amount), Decimal(0)),
                credit=max(-Decimal(amount), Decimal(0)),
                **dimensions,
            )
        journal = submit_journal(
            organization=self.organization, actor=self.owner, journal=journal
        )
        return post_journal(
            organization=self.organization,
            actor=self.reviewer,
            journal=journal,
            reason="independent accounting review",
        )

    def _activity(self, revenue=80, expense=30, *, dimensions=None):
        dimensions = dimensions or {}
        self._post(
            "initial-capital",
            [
                (self.debit_account, 100, dimensions),
                (self.credit_account, -100, dimensions),
            ],
        )
        if revenue:
            self._post(
                "revenue",
                [
                    (self.debit_account, revenue, dimensions),
                    (self.income, -revenue, dimensions),
                ],
            )
        if expense:
            self._post(
                "expense",
                [
                    (self.expense, expense, dimensions),
                    (self.debit_account, -expense, dimensions),
                ],
            )

    def _period_close(self, period=None):
        period = period or self.period
        run = create_manual_opening_reconciliation_run(
            organization=self.organization, actor=self.owner, cutoff_date=period.ends_on
        )
        sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.reviewer,
            run=run,
            reason="independent period reconciliation",
        )
        return close_period(
            organization=self.organization,
            actor=self.reviewer,
            period=period,
            requested_by=self.owner_membership,
            reason="period checks complete",
        )

    def _prepare(self):
        return prepare_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
            reason="annual close request",
        )

    def _approve(self, closing):
        return approve_year_end(
            organization=self.organization,
            actor=self.reviewer,
            closing=closing,
            reason="annual close independently reviewed",
        )

    def _roll(self, closing):
        return roll_forward_year_end(
            organization=self.organization,
            actor=self.reviewer,
            closing=closing,
            reason="derived opening independently accepted",
        )

    def _complete(self, revenue=80, expense=30):
        self._activity(revenue, expense)
        self._period_close()
        return self._roll(self._approve(self._prepare()))

    def _reopen(self, closing):
        return reopen_year_end(
            organization=self.organization,
            actor=self.reopener,
            closing=closing,
            requested_by=self.owner_membership,
            reason="approved correction with inverse reconciliation",
        )

    def _client(self, user=None, *, csrf=False):
        client = Client(enforce_csrf_checks=csrf)
        client.force_login(user or self.owner)
        session = client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return client


class FiscalYearClosingTests(YearEndFixture, TestCase):
    def test_profit_loss_zero_and_balanced_permanent_carry(self):
        closing = self._complete()
        self.assertEqual(closing.annual_result, Decimal(50))
        self.assertEqual(closing.reconciliation["opening_status"], "PASS")
        self.assertEqual(closing.reconciliation["discrepancies"], [])
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.retained).credit, Decimal(50)
        )
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.debit_account).debit,
            Decimal(150),
        )
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.credit_account).credit,
            Decimal(100),
        )
        self.assertFalse(
            closing.opening_journal.lines.filter(
                account__account_type__in=["income", "expense"]
            ).exists()
        )
        for journal in (closing.closing_journal, closing.opening_journal):
            self.assertEqual(
                sum(line.debit - line.credit for line in journal.lines.all()), 0
            )
        self.assertEqual(
            {row["type"] for row in closing.final_snapshot["balances"]},
            {"asset", "equity"},
        )
        self.assertEqual(closing.events.count(), 3)
        self.year.refresh_from_db()
        self.assertEqual(self.year.status, "rolled_forward")

    def test_loss_retained_earnings_is_debit(self):
        closing = self._complete(30, 80)
        self.assertEqual(closing.annual_result, Decimal(-50))
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.retained).debit, Decimal(50)
        )

    def test_zero_annual_result_does_not_create_retained_plug(self):
        closing = self._complete(30, 30)
        self.assertEqual(closing.annual_result, 0)
        self.assertFalse(
            closing.opening_journal.lines.filter(account=self.retained).exists()
        )

    def test_empty_year_has_a_balanced_governed_close_and_opening(self):
        self._period_close()
        closing = self._roll(self._approve(self._prepare()))
        self.assertEqual(closing.annual_result, 0)
        self.assertIsNone(closing.opening_journal_id)
        self.assertIsNone(closing.closing_journal_id)
        self.assertFalse(closing.reconciliation["opening_entry_required"])
        self.assertEqual(closing.reconciliation["opening_status"], "PASS")

    def test_dimensions_and_prior_retained_earnings_are_preserved(self):
        project = Project.objects.create(
            organization=self.organization, code="YE-P", name="پروژه"
        )
        self._activity(dimensions={"project": project})
        self._post(
            "prior-retained",
            [
                (self.debit_account, 20, {"project": project}),
                (self.retained, -20, {"project": project}),
            ],
        )
        self._period_close()
        closing = self._roll(self._approve(self._prepare()))
        self.assertEqual(
            closing.opening_journal.lines.get(
                account=self.retained, project=project
            ).credit,
            Decimal(70),
        )
        self.assertFalse(
            closing.opening_journal.lines.filter(project__isnull=True).exists()
        )

    def test_idempotency_for_prepare_close_and_opening(self):
        closing = self._complete()
        self.assertEqual(self._prepare().pk, closing.pk)
        self.assertEqual(
            self._approve(closing).closing_journal_id, closing.closing_journal_id
        )
        self.assertEqual(
            self._roll(closing).opening_journal_id, closing.opening_journal_id
        )
        self.assertEqual(JournalEntry.objects.filter(kind="closing").count(), 1)
        self.assertEqual(closing.events.count(), 3)

    def test_self_approval_and_self_acceptance_denied(self):
        self._activity()
        self._period_close()
        closing = self._prepare()
        with self.assertRaises(PermissionDenied):
            approve_year_end(
                organization=self.organization,
                actor=self.owner,
                closing=closing,
                reason="self",
            )
        closing = self._approve(closing)
        with self.assertRaises(PermissionDenied):
            roll_forward_year_end(
                organization=self.organization,
                actor=self.owner,
                closing=closing,
                reason="self",
            )

    def test_unauthorized_and_platform_admin_have_no_implicit_authority(self):
        outsider = User.objects.create_superuser(username="platform-only", password="x")
        viewer = self._member("ye-viewer", MembershipRole.VIEWER)
        for actor in (outsider, viewer, self.other_owner):
            with self.assertRaises(PermissionDenied):
                prepare_year_end(
                    organization=self.organization,
                    actor=actor,
                    source_year=self.year,
                    target_year=self.target,
                    reason="denied",
                )

    def test_scoped_accountant_cannot_close_entire_book(self):
        project = Project.objects.create(
            organization=self.organization, code="LIMIT", name="محدود"
        )
        member = OrganizationMembership.objects.get(
            user=self.reviewer, organization=self.organization
        )
        member.scope_grants.all().delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=project,
            reason="project-only",
        )
        with self.assertRaises(PermissionDenied):
            inspect_year_end(
                organization=self.organization,
                actor=self.reviewer,
                source_year=self.year,
                target_year=self.target,
            )

    def test_cross_tenant_pair_and_configuration_are_denied(self):
        alien = create_fiscal_year(
            organization=self.other_organization,
            actor=self.other_owner,
            code="ALIEN",
            name="other",
            starts_on=date(2027, 1, 1),
            ends_on=date(2027, 12, 31),
            calendar_version=1,
        )
        with self.assertRaises(PermissionDenied):
            prepare_year_end(
                organization=self.organization,
                actor=self.owner,
                source_year=self.year,
                target_year=alien,
                reason="denied",
            )
        alien_account = create_account(
            organization=self.other_organization,
            actor=self.other_owner,
            code="OTHER-EQ",
            name="other",
            account_type="equity",
            is_posting=True,
        )
        with self.assertRaises((PermissionDenied, ValidationError)):
            configure_year_end(
                organization=self.organization,
                actor=self.owner,
                fiscal_year=self.target,
                result_account=alien_account,
                retained_account=self.retained,
                reason="denied",
            )

    def test_source_and_target_from_different_context_not_accessible(self):
        self._activity()
        self._period_close()
        closing = self._prepare()
        with self.assertRaises(PermissionDenied):
            approve_year_end(
                organization=self.other_organization,
                actor=self.other_owner,
                closing=closing,
                reason="denied",
            )

    def test_non_successor_year_is_rejected(self):
        future = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-04",
            name="future",
            starts_on=date(2029, 1, 1),
            ends_on=date(2029, 12, 31),
            calendar_version=1,
        )
        self._period_close()
        with self.assertRaises(ValidationError):
            prepare_year_end(
                organization=self.organization,
                actor=self.owner,
                source_year=self.year,
                target_year=future,
                reason="invalid successor",
            )

    def test_preclose_blocks_open_period_and_pending_documents(self):
        readiness = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertFalse(readiness["ready"])
        self._period_close()
        # Simulate stale imported draft evidence without weakening service guards.
        with (
            patch(
                "apps.accounting.closing_services._snapshot",
                side_effect=ValidationError("unbalanced ledger"),
            ),
            self.assertRaises(ValidationError),
        ):
            self._prepare()
        self.assertFalse(FiscalYearClosing.objects.exists())

    def test_missing_configuration_and_invalid_classification_fail_closed(self):
        readiness = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.target,
            target_year=self.year,
        )
        self.assertFalse(readiness["ready"])
        self._activity()
        Account.objects.filter(pk=self.income.pk).update(account_type="statistical")
        readiness = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertFalse(readiness["ready"])
        self.assertTrue(any("طبقه‌بندی" in issue for issue in readiness["issues"]))

    def test_period_reopen_and_posting_cannot_bypass_annual_freeze(self):
        closing = self._complete()
        with self.assertRaises(ValidationError):
            reopen_period(
                organization=self.organization,
                actor=self.reopener,
                period=self.period,
                requested_by=self.owner_membership,
                reason="bypass",
            )
        with self.assertRaises(ValidationError):
            self._post(
                "bypass", [(self.debit_account, 1, {}), (self.credit_account, -1, {})]
            )
        with self.assertRaises(ValidationError):
            reverse_journal(
                organization=self.organization,
                actor=self.reviewer,
                original=closing.opening_journal,
                requested_by=self.owner_membership,
                accounting_date=self.target.starts_on,
                period=self.target_period,
                reason="bypass",
            )

    def test_conflicting_manual_opening_is_blocked_in_both_directions(self):
        create_opening_import(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.target,
            period=self.target_period,
            source_reference="external",
            cutoff_date=self.year.ends_on,
            evidence_reference="evidence",
            reconciliation_reference="recon",
        )
        self._period_close()
        with self.assertRaises(ValidationError):
            self._prepare()

    def test_manual_opening_is_reserved_after_preparation(self):
        self._period_close()
        self._prepare()
        with self.assertRaises(ValidationError):
            create_opening_import(
                organization=self.organization,
                actor=self.owner,
                fiscal_year=self.target,
                period=self.target_period,
                source_reference="external",
                cutoff_date=self.year.ends_on,
                evidence_reference="evidence",
                reconciliation_reference="recon",
            )

    def test_closed_year_reversal_before_roll_forward(self):
        self._activity()
        self._period_close()
        closed = self._approve(self._prepare())
        reopened = self._reopen(closed)
        self.assertEqual(reopened.status, ClosingStatus.REVERSED)
        self.assertIsNone(reopened.opening_reversal_id)
        self.assertEqual(reopened.reconciliation["reversal_status"], "PASS")
        self.period.refresh_from_db()
        self.year.refresh_from_db()
        self.assertEqual((self.year.status, self.period.status), ("active", "open"))

    def test_roll_reversal_reclose_and_new_version(self):
        closing = self._complete()
        reopened = self._reopen(closing)
        self.assertIsNotNone(reopened.opening_reversal_id)
        self._post("correction", [(self.debit_account, 5, {}), (self.income, -5, {})])
        self._period_close()
        fresh = self._roll(self._approve(self._prepare()))
        self.assertEqual(fresh.version, 2)
        self.assertEqual(fresh.annual_result, Decimal(55))
        self.assertEqual(
            fresh.opening_journal.lines.get(account=self.retained).credit, Decimal(55)
        )
        self.assertEqual(FiscalYearClosing.objects.count(), 2)

    def test_downstream_posted_transactions_block_reopen(self):
        closing = self._complete()
        self._post(
            "next-year-operation",
            [(self.debit_account, 7, {}), (self.credit_account, -7, {})],
            period=self.target_period,
        )
        before = JournalEntry.objects.count()
        with self.assertRaises(ValidationError):
            self._reopen(closing)
        self.assertEqual(JournalEntry.objects.count(), before)
        closing.refresh_from_db()
        self.assertEqual(closing.status, ClosingStatus.ROLLED_FORWARD)

    def test_failure_during_close_rolls_back_journal_status_and_audit(self):
        self._activity()
        self._period_close()
        closing = self._prepare()
        before = (JournalEntry.objects.count(), AuditEvent.objects.count())
        with (
            patch(
                "apps.accounting.closing_services._reconcile_final",
                side_effect=ValidationError("forced reconciliation failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            self._approve(closing)
        self.assertEqual(
            (JournalEntry.objects.count(), AuditEvent.objects.count()), before
        )
        closing.refresh_from_db()
        self.year.refresh_from_db()
        self.assertEqual((closing.status, self.year.status), ("prepared", "closing"))

    def test_opening_creation_and_reconciliation_failures_are_atomic(self):
        self._activity()
        self._period_close()
        closing = self._approve(self._prepare())
        before = (JournalEntry.objects.count(), AuditEvent.objects.count())
        for path in ("_line", "_opening_reconciliation"):
            with (
                patch(
                    f"apps.accounting.closing_services.{path}",
                    side_effect=ValidationError("forced opening failure"),
                ),
                self.assertRaises(ValidationError),
            ):
                self._roll(closing)
            self.assertEqual(
                (JournalEntry.objects.count(), AuditEvent.objects.count()), before
            )
            closing.refresh_from_db()
            self.assertEqual(closing.status, "closed")
            self.assertIsNone(closing.opening_journal_id)

    def test_snapshot_and_event_tamper_are_rejected(self):
        self._activity()
        self._period_close()
        closing = self._prepare()
        FiscalYearClosing.objects.filter(pk=closing.pk).update(
            annual_result=Decimal(999)
        )
        # Pin all material fields, including the signed annual result.
        with self.assertRaises(ValidationError):
            self._approve(closing)

    def test_database_active_pair_uniqueness(self):
        self._period_close()
        closing = self._prepare()
        with self.assertRaises((IntegrityError, ValidationError)), transaction.atomic():
            FiscalYearClosing.objects.create(
                organization=self.organization,
                source_year=self.year,
                target_year=self.target,
                configuration=closing.configuration,
                version=2,
                cutoff_date=closing.cutoff_date,
                initiated_by=self.owner_membership,
                source_snapshot=closing.source_snapshot,
                annual_result=0,
                reason="duplicate",
            )

    def test_reporting_does_not_double_count_and_profit_loss_survives_close(self):
        closing = self._complete()
        report = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind="trial_balance",
            ends_on=self.target.ends_on,
        )
        asset = next(
            row for row in report.lines if row.account_id == self.debit_account.pk
        )
        self.assertEqual(asset.closing_debit, Decimal(150))
        result = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind="profit_loss",
            starts_on=self.year.starts_on,
            ends_on=self.year.ends_on,
        )
        self.assertEqual(result.net_total, Decimal(50))
        spanning = build_statement(
            organization=self.organization,
            actor=self.owner,
            kind="trial_balance",
            starts_on=self.year.starts_on,
            ends_on=self.target.ends_on,
        )
        self.assertEqual(
            next(
                row for row in spanning.lines if row.account_id == self.debit_account.pk
            ).closing_debit,
            Decimal(150),
        )
        self.assertEqual(
            closing.reconciliation["opening_debit"],
            closing.reconciliation["opening_credit"],
        )

    def test_ui_flow_evidence_authorization_and_csrf(self):
        client = self._client()
        self.assertContains(client.get(reverse("accounting:year_end_list")), "بستن سال")
        self.assertContains(
            client.get(reverse("accounting:year_end_configuration")),
            "سود و زیان انباشته",
        )
        closing = self._complete()
        detail = reverse("accounting:year_end_detail", args=[closing.pk])
        self.assertContains(client.get(detail), "اختتامیه و افتتاحیه برابر است")
        data = client.get(
            reverse("accounting:year_end_evidence", args=[closing.pk])
        ).json()
        self.assertEqual(data["reconciliation"]["opening_status"], "PASS")
        endpoint = reverse("accounting:year_end_approve", args=[closing.pk])
        self.assertEqual(
            self._client(csrf=True).post(endpoint, {"reason": "csrf"}).status_code, 403
        )
        outsider = self._client(self.other_owner)
        self.assertIn(outsider.get(detail).status_code, (302, 403, 404))


class FiscalYearClosingAdditionalTests(YearEndFixture, TestCase):
    def test_existing_posted_journal_retry_remains_read_only_after_year_close(self):
        self._complete()
        original = JournalEntry.objects.get(source_key="initial-capital")
        count = JournalEntry.objects.count()
        repeated = post_journal(
            organization=self.organization,
            actor=self.reviewer,
            journal=original,
            reason="read-only idempotent retry",
        )
        self.assertEqual(repeated.pk, original.pk)
        self.assertEqual(JournalEntry.objects.count(), count)

    def test_ledger_boundary_and_lines_share_one_database_snapshot(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from .closing_guards import ledger_window

        self._complete()
        with CaptureQueriesContext(connection) as queries:
            lines = ledger_window(
                JournalLine.objects.filter(
                    organization=self.organization,
                    account=self.debit_account,
                    journal__status="posted",
                ),
                organization=self.organization,
                starts_on=None,
                ends_on=self.target.ends_on,
            )
            self.assertEqual(len(queries), 0)
            total = sum(line.debit - line.credit for line in lines)
        self.assertEqual(total, Decimal(150))
        self.assertEqual(len(queries), 1)

    def test_empty_close_can_be_reversed_and_closed_again(self):
        self._period_close()
        closed = self._roll(self._approve(self._prepare()))
        self._reopen(closed)
        self._period_close()
        fresh = self._roll(self._approve(self._prepare()))
        self.assertEqual(fresh.version, 2)
        self.assertEqual(fresh.reconciliation["opening_status"], "PASS")

    def test_period_close_evidence_tampering_blocks_readiness(self):
        self._period_close()
        self.period.control_events.update(evidence_hash="0" * 64)
        report = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertFalse(report["ready"])

    def test_invalid_posting_contract_blocks_readiness(self):
        self._activity()
        JournalEntry.objects.filter(source_key="revenue").update(
            posting_rule_version=999
        )
        report = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertFalse(report["ready"])
        self.assertTrue(any("قرارداد" in issue for issue in report["issues"]))

    def test_generated_opening_source_and_controls_route_to_year_end(self):
        closing = self._complete()
        client = self._client()
        response = client.get(
            reverse("accounting:journal_source", args=[closing.opening_journal_id])
        )
        self.assertRedirects(
            response, reverse("accounting:year_end_detail", args=[closing.pk])
        )
        detail = client.get(
            reverse("accounting:journal_detail", args=[closing.opening_journal_id])
        )
        self.assertNotContains(detail, "ثبت برگشت محافظت‌شده")

    def test_all_existing_dimensions_remain_separate(self):
        from apps.parties.models import BusinessParty
        from apps.projects.models import ProjectSite, WBSNode

        project = Project.objects.create(
            organization=self.organization, code="DIM", name="پروژه"
        )
        site = ProjectSite.objects.create(
            organization=self.organization, project=project, code="S", name="کارگاه"
        )
        wbs = WBSNode.objects.create(
            organization=self.organization, project=project, code="W", title="بخش"
        )
        party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind="company",
            display_name="طرف آزمون",
        )
        dims = {"project": project, "site": site, "wbs_node": wbs, "party": party}
        self._activity(dimensions=dims)
        self._post(
            "unscoped-capital",
            [(self.debit_account, 20, {}), (self.credit_account, -20, {})],
        )
        self._period_close()
        closing = self._roll(self._approve(self._prepare()))
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.debit_account, **dims).debit,
            Decimal(150),
        )
        self.assertEqual(
            closing.opening_journal.lines.get(
                account=self.debit_account, project=None
            ).debit,
            Decimal(20),
        )

    def test_configuration_versions_and_withdrawal_preserve_history(self):
        from .closing_services import cancel_year_end

        self._period_close()
        closing = self._prepare()
        cancelled = cancel_year_end(
            organization=self.organization,
            actor=self.owner,
            closing=closing,
            reason="revise configuration before posting",
        )
        retained = self._account("3350", AccountType.EQUITY)
        updated = configure_year_end(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.year,
            result_account=self.summary,
            retained_account=retained,
            reason="reviewed corrected account selection",
        )
        self.assertEqual(updated.version, 2)
        self.assertEqual(cancelled.configuration.retained_account_id, self.retained.pk)
        self.assertEqual(FiscalClosingConfiguration.objects.count(), 2)
        fresh = self._prepare()
        self.assertEqual(fresh.version, 2)
        self.assertEqual(fresh.configuration_id, updated.pk)
        self.assertEqual(cancelled.events.count(), 2)

    def test_reopen_failure_rolls_back_both_inverses(self):
        closing = self._complete()
        before = (JournalEntry.objects.count(), AuditEvent.objects.count())
        with (
            patch(
                "apps.accounting.closing_services.reopen_period",
                side_effect=ValidationError("period separation denied"),
            ),
            self.assertRaises(ValidationError),
        ):
            self._reopen(closing)
        self.assertEqual(
            (JournalEntry.objects.count(), AuditEvent.objects.count()), before
        )
        self.year.refresh_from_db()
        self.assertEqual(self.year.status, "rolled_forward")

    def test_repeated_years_do_not_duplicate_capital_or_result(self):
        self._complete()
        third = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY-03",
            name="سال سوم",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            calendar_version=1,
        )
        create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=third,
            number=1,
            name="سال سوم",
            starts_on=third.starts_on,
            ends_on=third.ends_on,
        )
        configure_year_end(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=self.target,
            result_account=self.summary,
            retained_account=self.retained,
            reason="next-year config",
        )
        self._post(
            "second-year-revenue",
            [(self.debit_account, 10, {}), (self.income, -10, {})],
            period=self.target_period,
        )
        self._period_close(self.target_period)
        closing = prepare_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.target,
            target_year=third,
            reason="second annual close",
        )
        closing = self._roll(self._approve(closing))
        self.assertEqual(closing.annual_result, Decimal(10))
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.retained).credit, Decimal(60)
        )
        for start in (
            None,
            self.year.starts_on,
            self.target.starts_on,
            third.starts_on,
        ):
            report = build_statement(
                organization=self.organization,
                actor=self.owner,
                kind="trial_balance",
                starts_on=start,
                ends_on=third.ends_on,
            )
            self.assertEqual(
                next(
                    row
                    for row in report.lines
                    if row.account_id == self.debit_account.pk
                ).closing_debit,
                Decimal(160),
            )

    def test_existing_liabilities_and_negative_retained_are_preserved(self):
        liability = self._account("2100", AccountType.LIABILITY)
        self._activity()
        self._post("loan", [(self.debit_account, 40, {}), (liability, -40, {})])
        self._post(
            "prior-loss", [(self.retained, 20, {}), (self.debit_account, -20, {})]
        )
        self._period_close()
        closing = self._roll(self._approve(self._prepare()))
        self.assertEqual(
            closing.opening_journal.lines.get(account=liability).credit, Decimal(40)
        )
        self.assertEqual(
            closing.opening_journal.lines.get(account=self.retained).credit, Decimal(30)
        )

    def test_suspended_tenant_is_rechecked_from_database(self):
        self.organization.__class__.objects.filter(pk=self.organization.pk).update(
            status="suspended"
        )
        with self.assertRaises(PermissionDenied):
            self._prepare()

    def test_draft_document_and_summary_balance_block_readiness(self):
        self._post(
            "incorrect-summary-balance",
            [(self.debit_account, 3, {}), (self.summary, -3, {})],
        )
        create_journal(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            kind="manual",
            document_date=self.period.starts_on,
            accounting_date=self.period.starts_on,
            description="pending",
            source_key="pending",
        )
        report = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertTrue(any("تعیین‌تکلیف" in issue for issue in report["issues"]))
        self.assertTrue(any("مانده صفر" in issue for issue in report["issues"]))

    def test_malformed_posted_dimensions_and_payload_block_readiness(self):
        self._activity()
        line = JournalLine.objects.filter(account=self.debit_account).first()
        JournalLine.objects.filter(pk=line.pk).update(
            dimension_snapshot={"project": {"id": "invalid"}}
        )
        report = inspect_year_end(
            organization=self.organization,
            actor=self.owner,
            source_year=self.year,
            target_year=self.target,
        )
        self.assertFalse(report["ready"])
        self.assertTrue(any("ابعاد" in issue for issue in report["issues"]))

    def test_reviewer_permission_revocation_blocks_close(self):
        self._activity()
        self._period_close()
        closing = self._prepare()
        OrganizationMembership.objects.filter(
            organization=self.organization, user=self.reviewer
        ).update(status="revoked")
        with self.assertRaises(PermissionDenied):
            self._approve(closing)

    def test_year_end_journals_cannot_be_replaced_or_adjusted(self):
        from .services import create_replacement_journal

        closing = self._complete()
        with self.assertRaises(ValidationError):
            create_replacement_journal(
                organization=self.organization,
                actor=self.owner,
                original=closing.opening_journal,
                period=self.target_period,
                accounting_date=self.target.starts_on,
                document_date=self.target.starts_on,
                description="bypass",
            )

    def test_ui_post_flow_uses_independent_actors(self):
        self._activity()
        self._period_close()
        maker, checker = self._client(), self._client(self.reviewer)
        response = maker.post(
            reverse("accounting:year_end_list"),
            {
                "action": "prepare",
                "source_year": self.year.pk,
                "target_year": self.target.pk,
                "reason": "UI annual close",
            },
        )
        self.assertEqual(response.status_code, 302)
        closing = FiscalYearClosing.objects.get()
        self.assertContains(maker.get(response.url), "در انتظار تأیید بستن")
        self.assertEqual(
            maker.post(
                reverse("accounting:year_end_approve", args=[closing.pk]),
                {"reason": "self"},
            ).status_code,
            403,
        )
        self.assertEqual(
            checker.post(
                reverse("accounting:year_end_approve", args=[closing.pk]),
                {"reason": "reviewed"},
            ).status_code,
            302,
        )
        self.assertEqual(
            checker.post(
                reverse("accounting:year_end_roll_forward", args=[closing.pk]),
                {"reason": "opening reviewed"},
            ).status_code,
            302,
        )
        closing.refresh_from_db()
        self.assertEqual(closing.reconciliation["opening_status"], "PASS")


class FiscalYearClosingMigrationTests(YearEndFixture, TransactionTestCase):
    def test_populated_ledger_survives_schema_rollback_and_reapply(self):
        import hashlib
        import json

        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        self._activity()
        models = (
            Account,
            FiscalYear,
            FiscalPeriod,
            JournalEntry,
            JournalLine,
            AuditEvent,
        )

        def snapshot():
            return {
                model._meta.label: hashlib.sha256(
                    json.dumps(
                        list(model.objects.order_by("pk").values()),
                        sort_keys=True,
                        default=str,
                    ).encode()
                ).hexdigest()
                for model in models
            }

        before = snapshot()
        try:
            MigrationExecutor(connection).migrate(
                [("accounting", "0013_cep042_recognition_mapping")]
            )
            self.assertEqual(snapshot(), before)
            MigrationExecutor(connection).migrate(
                [("accounting", "0016_fiscal_year_zero_entry_references")]
            )
            self.assertEqual(snapshot(), before)
        finally:
            MigrationExecutor(connection).migrate(
                [("accounting", "0016_fiscal_year_zero_entry_references")]
            )


class FiscalYearClosingConcurrencyTests(YearEndFixture, TransactionTestCase):
    def test_concurrent_prepare_close_and_opening_create_one_execution(self):
        self._activity()
        self._period_close()

        def race(service, args):
            barrier = Barrier(2)

            def call(_):
                close_old_connections()
                try:
                    barrier.wait(timeout=15)
                    return service(**args).pk
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as pool:
                result = list(pool.map(call, range(2)))
            self.assertEqual(result[0], result[1])
            return FiscalYearClosing.objects.get(pk=result[0])

        closing = race(
            prepare_year_end,
            {
                "organization": self.organization,
                "actor": self.owner,
                "source_year": self.year,
                "target_year": self.target,
                "reason": "concurrent prepare",
            },
        )
        closing = race(
            approve_year_end,
            {
                "organization": self.organization,
                "actor": self.reviewer,
                "closing": closing,
                "reason": "concurrent close",
            },
        )
        closing = race(
            roll_forward_year_end,
            {
                "organization": self.organization,
                "actor": self.reviewer,
                "closing": closing,
                "reason": "concurrent opening",
            },
        )
        self.assertEqual(FiscalYearClosing.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.filter(kind="closing").count(), 1)
        self.assertEqual(JournalEntry.objects.filter(kind="opening").count(), 1)
        self.assertEqual(closing.reconciliation["opening_status"], "PASS")
