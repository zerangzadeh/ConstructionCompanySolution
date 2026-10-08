from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from queue import Queue
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.daily_reports.models import DailyReport, DailyReportStatus
from apps.daily_reports.services import approve_daily_report, submit_daily_report
from apps.estimates.models import Estimate, EstimateStatus
from apps.estimates.services import approve_estimate
from apps.expenses.models import Expense, ExpenseStatus
from apps.expenses.services import void_expense
from apps.inventory.models import StockTransaction, StockTransactionType
from apps.inventory.services import (
    create_stock_transaction,
    create_warehouse,
    get_stock_balance,
    post_stock_transaction,
)
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.payments.models import Payment, PaymentDirection, PaymentStatus
from apps.payments.services import void_payment
from apps.projects.models import (
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
)
from apps.projects.services import transition_project_phase_status


class PostgreSQLSelectForUpdateConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics are required.")

        self.owner = User.objects.create_user(username="lock-owner", password="test")
        self.organization = Organization.objects.create(
            name="Locking Company",
            slug="locking-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="LOCK-PROJECT",
            name="Lock project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="LOCK-SITE",
            name="Lock site",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.active_phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="LOCK-ACTIVE",
            name="Active phase",
            status=ProjectPhaseStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.planning_phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="LOCK-PLANNING",
            name="Planning phase",
            status=ProjectPhaseStatus.PLANNING,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.estimate = Estimate.objects.create(
            organization=self.organization,
            project=self.project,
            estimate_number="LOCK-ESTIMATE",
            title="Lock estimate",
            status=EstimateStatus.DRAFT,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.daily_report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.active_phase,
            reporting_date=date(2026, 9, 3),
            work_performed="Lock validation",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.expense = Expense.objects.create(
            organization=self.organization,
            project=self.project,
            phase=self.active_phase,
            description="Lock expense",
            amount=Decimal("10.00"),
            incurred_on=date(2026, 9, 3),
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.payment = Payment.objects.create(
            organization=self.organization,
            project=self.project,
            phase=self.active_phase,
            payment_number="LOCK-PAYMENT",
            direction=PaymentDirection.DISBURSEMENT,
            amount=Decimal("10.00"),
            paid_on=date(2026, 9, 3),
            counterparty_name="Lock supplier",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.inventory_unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="LOCK-KG",
            name="Lock kilogram",
            symbol="lock-kg",
            category=UnitCategory.WEIGHT,
            decimal_places=4,
        )
        self.inventory_material = Material.objects.create(
            organization=self.organization,
            code="LOCK-MATERIAL",
            name="Lock material",
            unit_of_measure=self.inventory_unit,
        )
        self.inventory_warehouse = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="LOCK-WAREHOUSE",
            name="Lock warehouse",
        )
        opening = create_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            transaction_number="LOCK-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            destination_warehouse=self.inventory_warehouse,
            material=self.inventory_material,
            unit_of_measure=self.inventory_unit,
            quantity=Decimal("10.0000"),
            occurred_at=timezone.now(),
        )
        post_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=opening,
        )

    def _run_race(self, action: Callable[[], object]) -> list[ValueError | None]:
        barrier = Barrier(2)
        results: Queue[ValueError | None] = Queue()

        def runner() -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                action()
            except ValueError as exc:
                results.put(exc)
            else:
                results.put(None)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(runner) for _ in range(2)]
            for future in futures:
                future.result(timeout=30)

        return [results.get_nowait(), results.get_nowait()]

    def _assert_one_success_and_one_state_rejection(
        self,
        results: list[ValueError | None],
    ) -> None:
        self.assertEqual(results.count(None), 1, results)
        failures = [result for result in results if result is not None]
        self.assertEqual(len(failures), 1, results)
        self.assertIsInstance(failures[0], ValueError)

    def test_concurrent_estimate_approval_has_one_winner(self) -> None:
        def approve() -> object:
            return approve_estimate(
                estimate=Estimate.objects.get(pk=self.estimate.pk),
                actor=User.objects.get(pk=self.owner.pk),
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(approve))

        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.status, EstimateStatus.APPROVED)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.ESTIMATE_APPROVED,
                entity_id=str(self.estimate.pk),
            ).count(),
            1,
        )

    def test_concurrent_daily_report_submit_and_approve_each_have_one_winner(
        self,
    ) -> None:
        def submit() -> object:
            return submit_daily_report(
                organization=Organization.objects.get(pk=self.organization.pk),
                report_id=str(self.daily_report.pk),
                actor=User.objects.get(pk=self.owner.pk),
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(submit))
        self.daily_report.refresh_from_db()
        self.assertEqual(self.daily_report.status, DailyReportStatus.SUBMITTED)

        def approve() -> object:
            return approve_daily_report(
                organization=Organization.objects.get(pk=self.organization.pk),
                report_id=str(self.daily_report.pk),
                actor=User.objects.get(pk=self.owner.pk),
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(approve))
        self.daily_report.refresh_from_db()
        self.assertEqual(self.daily_report.status, DailyReportStatus.APPROVED)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.DAILY_REPORT_SUBMITTED,
                entity_id=str(self.daily_report.pk),
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.DAILY_REPORT_APPROVED,
                entity_id=str(self.daily_report.pk),
            ).count(),
            1,
        )

    def test_concurrent_expense_void_has_one_winner(self) -> None:
        def void() -> object:
            return void_expense(
                expense=Expense.objects.get(pk=self.expense.pk),
                actor=User.objects.get(pk=self.owner.pk),
                reason="Duplicate request race",
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(void))

        self.expense.refresh_from_db()
        self.assertEqual(self.expense.status, ExpenseStatus.VOID)
        self.assertEqual(self.expense.amount, Decimal("10.00"))
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.EXPENSE_VOIDED,
                entity_id=str(self.expense.pk),
            ).count(),
            1,
        )

    def test_concurrent_payment_void_has_one_winner(self) -> None:
        def void() -> object:
            return void_payment(
                payment=Payment.objects.get(pk=self.payment.pk),
                actor=User.objects.get(pk=self.owner.pk),
                reason="Duplicate request race",
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(void))

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.VOID)
        self.assertEqual(self.payment.amount, Decimal("10.00"))
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.PAYMENT_VOIDED,
                entity_id=str(self.payment.pk),
            ).count(),
            1,
        )

    def test_concurrent_phase_transition_has_one_winner(self) -> None:
        def transition() -> object:
            return transition_project_phase_status(
                organization=Organization.objects.get(pk=self.organization.pk),
                project_id=str(self.project.pk),
                site_id=str(self.site.pk),
                phase_id=str(self.planning_phase.pk),
                actor=User.objects.get(pk=self.owner.pk),
                target_status=ProjectPhaseStatus.ACTIVE,
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(transition))

        self.planning_phase.refresh_from_db()
        self.assertEqual(self.planning_phase.status, ProjectPhaseStatus.ACTIVE)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.PROJECT_PHASE_STATUS_CHANGED,
                entity_id=str(self.planning_phase.pk),
            ).count(),
            1,
        )

    def test_concurrent_stock_issues_cannot_overdraw_warehouse(self) -> None:
        transaction_ids: Queue = Queue()
        for index in range(2):
            draft = create_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                transaction_number=f"LOCK-ISSUE-{index}",
                transaction_type=StockTransactionType.ISSUE,
                source_warehouse=self.inventory_warehouse,
                material=self.inventory_material,
                unit_of_measure=self.inventory_unit,
                project=self.project,
                quantity=Decimal("6.0000"),
                occurred_at=timezone.now(),
            )
            transaction_ids.put(draft.pk)

        def post_issue() -> object:
            return post_stock_transaction(
                organization=Organization.objects.get(pk=self.organization.pk),
                actor=User.objects.get(pk=self.owner.pk),
                stock_transaction=StockTransaction.objects.get(
                    pk=transaction_ids.get_nowait()
                ),
            )

        self._assert_one_success_and_one_state_rejection(self._run_race(post_issue))
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.inventory_warehouse,
                material=self.inventory_material,
            ),
            Decimal("4.0000"),
        )
