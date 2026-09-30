from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from queue import Queue
from threading import Barrier

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounting import tests as accounting_test_support
from apps.accounting.models import (
    FinancialStatementKind,
    FinancialStatementRun,
    FiscalPeriodControlEvent,
    FiscalPeriodStatus,
    JournalEntry,
    JournalKind,
    JournalNumberSequence,
    ReconciliationRun,
)
from apps.accounting.reconciliation import (
    create_manual_opening_reconciliation_run,
    sign_off_reconciliation_run,
)
from apps.accounting.reporting import retain_statement
from apps.accounting.services import (
    add_journal_line,
    close_period,
    create_controlled_adjustment,
    create_fiscal_period,
    create_journal,
    post_journal,
    reopen_period,
    reverse_journal,
    submit_journal,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)


class AccountingFinancialHardeningTests(TransactionTestCase):
    """PostgreSQL acceptance for the bounded P2-S35--S36 contract."""

    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def _activate_policy(self, *args, **kwargs) -> None:
        accounting_test_support.AccountingPostingConcurrencyTests._activate_policy(
            self, *args, **kwargs
        )

    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics are required.")
        accounting_test_support.AccountingPostingConcurrencyTests.setUp(self)

    def _member(self, username: str, role_code: str) -> tuple[User, OrganizationMembership]:
        user = User.objects.create_user(username=username, password="x")
        role = OrganizationRole.objects.get(
            code=role_code, organization__isnull=True
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=role_code,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="P2 financial hardening test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P2 financial hardening test",
        )
        return user, membership

    def _parallel(self, operations):
        barrier = Barrier(len(operations))
        outcomes: Queue[object] = Queue()

        def runner(operation) -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    outcomes.put(("ok", operation()))
                except Exception as exc:  # noqa: BLE001 - assertions inspect race outcome
                    outcomes.put(("error", exc))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            futures = [executor.submit(runner, operation) for operation in operations]
            for future in futures:
                future.result(timeout=30)
        return [outcomes.get_nowait() for _ in operations]

    def _post_seed_journal(self) -> JournalEntry:
        return post_journal(
            organization=self.organization,
            actor=self.approver,
            journal=self.journal,
            reason="independent seed posting",
        )

    def _signed_reconciliation(self) -> ReconciliationRun:
        run = create_manual_opening_reconciliation_run(
            organization=self.organization,
            actor=self.owner,
            cutoff_date=date(2026, 1, 31),
        )
        sign_off_reconciliation_run(
            organization=self.organization,
            actor=self.approver,
            run=run,
            reason="independent period evidence review",
        )
        return run

    def _second_proposed_journal(self) -> JournalEntry:
        period = self.journal.period
        journal = create_journal(
            organization=self.organization,
            actor=self.owner,
            period=period,
            kind=JournalKind.MANUAL,
            document_date=date(2026, 1, 3),
            accounting_date=date(2026, 1, 3),
            description="second concurrent posting",
            source_key="RACE-POST-SECOND",
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.journal.lines.get(line_number=1).account,
            line_number=1,
            debit=Decimal(20),
        )
        add_journal_line(
            organization=self.organization,
            actor=self.owner,
            journal=journal,
            account=self.journal.lines.get(line_number=2).account,
            line_number=2,
            credit=Decimal(20),
        )
        return submit_journal(
            organization=self.organization, actor=self.owner, journal=journal
        )

    def test_concurrent_distinct_posting_allocates_each_number_once(self) -> None:
        second = self._second_proposed_journal()

        def post(journal_id):
            return lambda: post_journal(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.approver.pk),
                journal=JournalEntry.objects.get(pk=journal_id),
                reason="concurrent independent posting",
            ).pk

        outcomes = self._parallel([post(self.journal.pk), post(second.pk)])
        self.assertTrue(all(status == "ok" for status, _ in outcomes), outcomes)
        numbers = set(
            JournalEntry.objects.filter(pk__in=[self.journal.pk, second.pk]).values_list(
                "number", flat=True
            )
        )
        self.assertEqual(numbers, {1, 2})
        self.assertEqual(
            JournalNumberSequence.objects.get(organization=self.organization).next_number,
            3,
        )

    def test_concurrent_identical_journal_creation_returns_one_draft(self) -> None:
        def create():
            return create_journal(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.owner.pk),
                period=type(self.journal.period).objects.get(pk=self.journal.period_id),
                kind=JournalKind.MANUAL,
                document_date=date(2026, 1, 5),
                accounting_date=date(2026, 1, 5),
                description="idempotent concurrent draft",
                source_key="RACE-CREATE-IDENTICAL",
            ).pk

        outcomes = self._parallel([create, create])
        self.assertTrue(all(status == "ok" for status, _ in outcomes), outcomes)
        self.assertEqual(outcomes[0][1], outcomes[1][1])
        journal = JournalEntry.objects.get(pk=outcomes[0][1])
        self.assertEqual(
            JournalEntry.objects.filter(
                organization=self.organization,
                source_key="RACE-CREATE-IDENTICAL",
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_JOURNAL_CREATED,
                entity_id=str(journal.pk),
            ).count(),
            1,
        )

    def test_concurrent_retained_statement_is_one_complete_run(self) -> None:
        self._post_seed_journal()

        def retain():
            return retain_statement(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.owner.pk),
                kind=FinancialStatementKind.TRIAL_BALANCE,
                starts_on=date(2026, 1, 1),
                ends_on=date(2026, 1, 31),
            ).pk

        outcomes = self._parallel([retain, retain])
        self.assertTrue(all(status == "ok" for status, _ in outcomes), outcomes)
        self.assertEqual(outcomes[0][1], outcomes[1][1])
        run = FinancialStatementRun.objects.get(pk=outcomes[0][1])
        self.assertEqual(run.lines.count(), 2)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_STATEMENT_RETAINED,
                entity_id=str(run.pk),
            ).count(),
            1,
        )

    def test_retained_statement_tampering_fails_closed_on_retry(self) -> None:
        self._post_seed_journal()
        run = retain_statement(
            organization=self.organization,
            actor=self.owner,
            kind=FinancialStatementKind.TRIAL_BALANCE,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run.lines.filter(sequence=1).update(amount=Decimal(999))

        with self.assertRaises(ValidationError):
            retain_statement(
                organization=self.organization,
                actor=self.owner,
                kind=FinancialStatementKind.TRIAL_BALANCE,
                starts_on=date(2026, 1, 1),
                ends_on=date(2026, 1, 31),
            )

    def test_stale_signed_cutoff_cannot_race_posting_into_a_close(self) -> None:
        self._post_seed_journal()
        self._signed_reconciliation()
        second = self._second_proposed_journal()

        def post_second():
            return post_journal(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.approver.pk),
                journal=JournalEntry.objects.get(pk=second.pk),
                reason="posting competing with close",
            ).pk

        def close():
            return close_period(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.approver.pk),
                period=type(self.journal.period).objects.get(pk=self.journal.period_id),
                requested_by=OrganizationMembership.objects.get(
                    pk=self.owner_membership.pk
                ),
                reason="close competing with posting",
            ).pk

        outcomes = self._parallel([post_second, close])
        self.assertEqual(sum(status == "ok" for status, _ in outcomes), 1, outcomes)
        error = next(value for status, value in outcomes if status == "error")
        self.assertIsInstance(error, ValidationError)
        self.journal.period.refresh_from_db()
        self.assertEqual(self.journal.period.status, FiscalPeriodStatus.OPEN)
        self.assertFalse(
            FiscalPeriodControlEvent.objects.filter(period=self.journal.period).exists()
        )

        self._signed_reconciliation()
        closed = close_period(
            organization=self.organization,
            actor=self.approver,
            period=self.journal.period,
            requested_by=self.owner_membership,
            reason="fresh reconciled close",
        )
        self.assertEqual(closed.status, FiscalPeriodStatus.CLOSED)

    def test_concurrent_close_reopen_and_adjustment_retries_are_idempotent(self) -> None:
        original = self._post_seed_journal()
        self._signed_reconciliation()

        def close():
            return close_period(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.approver.pk),
                period=type(original.period).objects.get(pk=original.period_id),
                requested_by=OrganizationMembership.objects.get(
                    pk=self.owner_membership.pk
                ),
                reason="idempotent period close",
            ).pk

        close_outcomes = self._parallel([close, close])
        self.assertTrue(
            all(status == "ok" for status, _ in close_outcomes), close_outcomes
        )
        self.assertEqual(
            FiscalPeriodControlEvent.objects.filter(
                period=original.period, action="close"
            ).count(),
            1,
        )

        reopen_actor, _ = self._member(
            "p2-hardening-reopen-owner", MembershipRole.TENANT_OWNER
        )

        def reopen():
            return reopen_period(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=reopen_actor.pk),
                period=type(original.period).objects.get(pk=original.period_id),
                requested_by=OrganizationMembership.objects.get(
                    pk=self.owner_membership.pk
                ),
                reason="idempotent period reopen",
            ).pk

        reopen_outcomes = self._parallel([reopen, reopen])
        self.assertTrue(
            all(status == "ok" for status, _ in reopen_outcomes), reopen_outcomes
        )
        self.assertEqual(
            FiscalPeriodControlEvent.objects.filter(period=original.period).count(), 2
        )

        # Re-close before exercising the only permitted late-adjustment path.
        self._signed_reconciliation()
        close_period(
            organization=self.organization,
            actor=self.approver,
            period=original.period,
            requested_by=self.owner_membership,
            reason="close before controlled adjustment",
        )
        adjustment_period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=original.period.fiscal_year,
            number=13,
            name="controlled adjustment period",
            starts_on=date(2026, 12, 31),
            ends_on=date(2026, 12, 31),
            is_adjustment=True,
        )

        def adjust():
            return create_controlled_adjustment(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.owner.pk),
                original=JournalEntry.objects.get(pk=original.pk),
                period=type(adjustment_period).objects.get(pk=adjustment_period.pk),
                document_date=date(2026, 12, 31),
                accounting_date=date(2026, 12, 31),
                description="concurrent controlled adjustment",
                source_key="RACE-CONTROLLED-ADJUSTMENT",
                reason="linked late correction",
                evidence_reference="evidence://p2-s35/adjustment",
                reconciliation_reference="reconciliation://p2-s35/adjustment",
            ).pk

        adjustment_outcomes = self._parallel([adjust, adjust])
        self.assertTrue(
            all(status == "ok" for status, _ in adjustment_outcomes),
            adjustment_outcomes,
        )
        self.assertEqual(adjustment_outcomes[0][1], adjustment_outcomes[1][1])
        adjustment = JournalEntry.objects.get(pk=adjustment_outcomes[0][1])
        self.assertEqual(adjustment.adjusts_id, original.pk)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_CONTROLLED_ADJUSTMENT_CREATED,
                entity_id=str(adjustment.pk),
            ).count(),
            1,
        )

    def test_concurrent_reversal_retry_creates_one_posted_correction(self) -> None:
        original = self._post_seed_journal()

        def reverse():
            return reverse_journal(
                organization=type(self.organization).objects.get(
                    pk=self.organization.pk
                ),
                actor=User.objects.get(pk=self.approver.pk),
                original=JournalEntry.objects.get(pk=original.pk),
                requested_by=OrganizationMembership.objects.get(
                    pk=self.owner_membership.pk
                ),
                accounting_date=date(2026, 1, 4),
                period=type(original.period).objects.get(pk=original.period_id),
                reason="concurrent linked reversal",
            ).pk

        outcomes = self._parallel([reverse, reverse])
        self.assertTrue(all(status == "ok" for status, _ in outcomes), outcomes)
        self.assertEqual(outcomes[0][1], outcomes[1][1])
        self.assertEqual(JournalEntry.objects.filter(reverses=original).count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ACCOUNTING_JOURNAL_REVERSED,
                entity_id=str(original.pk),
            ).count(),
            1,
        )


class AccountingMigrationRehearsalTests(TransactionTestCase):
    """Prove the latest bounded Accounting migration rolls back and reapplies."""

    reset_sequences = True
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def test_accounting_0009_rollback_and_reapply(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("The migration contract targets PostgreSQL.")
        before = ("accounting", "0008_reconciliationreview")
        latest = ("accounting", "0009_financial_statements_close_adjustments")
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([before])
            tables = set(connection.introspection.table_names())
            self.assertNotIn("accounting_financialstatementrun", tables)
            with connection.cursor() as cursor:
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(
                        cursor, "accounting_journalentry"
                    )
                }
            self.assertNotIn("adjusts_id", columns)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([latest])
        tables = set(connection.introspection.table_names())
        self.assertIn("accounting_financialstatementrun", tables)
        self.assertIn("accounting_fiscalperiodcontrolevent", tables)
        call_command("check", verbosity=0)
