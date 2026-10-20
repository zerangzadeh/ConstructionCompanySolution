"""Approved cash timing, lifecycle, scope, cutoff and reproducible-history proofs."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.projects import test_cep020_forecast_budget_control as fixtures
from apps.projects.cashflow import (
    capture_cashflow_comparison,
    digest,
    prepare_cashflow_supplement,
    rebuild_cashflow_snapshot,
    render_manifest,
)
from apps.projects.cashflow_models import (
    ProjectCashflowSnapshot,
    ProjectCashflowSupplement,
)
from apps.projects.forecast_governance import (
    forecast_submission_key,
    submit_project_cost_forecast,
)
from apps.projects.models import BudgetAllocation, ProjectForecastTransition
from apps.workflows.runtime import claim_work_item, complete_work_item


class CashflowTests(TestCase):
    setUp = fixtures.ForecastGovernanceTests.setUp
    _draft = fixtures.ForecastGovernanceTests._draft
    _classify_and_submit = fixtures.ForecastGovernanceTests._classify_and_submit
    _forecast = fixtures.ForecastGovernanceTests._forecast
    _workflow = fixtures.ForecastGovernanceTests._workflow

    def row(self, *, key="work-1", amount="100.000001", when="2026-10-01", **extra):
        source = BudgetAllocation.objects.get(
            manifest_line__manifest__budget=self.budget, sequence=1
        )
        return {
            "key": key,
            "economic_event_id": "work-1",
            "direction": "DISBURSEMENT",
            "source": {"family": "budget_allocation", "id": str(source.pk)},
            "cash_amount": amount,
            "expected_cash_on": when,
            "cash_basis": "Explicit approved cash planning amount; not estimated cost",
            "timing_basis": "Approved payment planning assumption CF-1/v1",
            "cost_cash_difference_evidence": "CF-1/v1 separately states cost/cash differences",
            **extra,
        }

    def supplement(self, forecast, rows=None):
        rows = [self.row()] if rows is None else rows
        controls = {}
        for row in rows:
            key = (
                row["source"]["family"] + ":" + row["source"]["id"],
                row["direction"],
            )
            controls.setdefault(key, {"cash_amount": Decimal(0), "row_count": 0})
            if row.get("state") == "cancelled":
                continue
            controls[key]["cash_amount"] += Decimal(row["cash_amount"])
            controls[key]["row_count"] += 1
        return prepare_cashflow_supplement(
            forecast=forecast,
            actor=self.preparer,
            rows=rows,
            controls=[
                {
                    "source_group": k[0],
                    "direction": k[1],
                    "currency": "IRR",
                    "cash_amount": str(v["cash_amount"]),
                    "row_count": v["row_count"],
                }
                for k, v in controls.items()
            ],
        )

    def approve(self, forecast):
        instance = submit_project_cost_forecast(
            forecast=forecast,
            actor=self.preparer,
            workflow_version=self.workflow,
            reason="Cash amounts, source controls and explicit dates reviewed",
            idempotency_key=forecast_submission_key(forecast),
        )
        item = instance.work_items.get()
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key=f"claim-{forecast.pk}",
        )
        complete_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            outcome="approved",
            idempotency_key=f"approve-{forecast.pk}",
            command_context={"reason": "Independent cash supplement acceptance"},
        )

    def ready(self, rows=None):
        self.workflow = self._workflow()
        f = self._forecast()
        s = self.supplement(f, rows)
        self.approve(f)
        return f, s

    def capture(self, baseline, forecast=None, **extra):
        return capture_cashflow_comparison(
            organization=self.organization,
            project=self.project,
            actor=self.approver,
            baseline_id=baseline.pk,
            forecast_id=(forecast or baseline).pk,
            knowledge_as_of=extra.pop("knowledge_as_of", timezone.now()),
            horizon_start=extra.pop("horizon_start", date(2026, 10, 1)),
            horizon_end=extra.pop("horizon_end", date(2026, 12, 1)),
            idempotency_key=extra.pop("idempotency_key", str(uuid4())),
            **extra,
        )

    def test_reviewed_monthly_comparison_retains_exact_cash_and_source_approval(self):
        f, s = self.ready()
        before = (
            self.project.estimated_budget,
            self.project.actual_budget,
            self.budget.payload_hash,
        )
        snapshot = self.capture(s)
        self.assertEqual(
            snapshot.result["buckets"]["2026-10-01"]["forecast"]["DISBURSEMENT"],
            "100.000001",
        )
        self.assertTrue(snapshot.result["complete"])
        self.assertEqual(
            snapshot.manifest["forecast"]["approval"]["actor_id"], str(self.approver.pk)
        )
        self.assertEqual(
            snapshot.manifest["forecast"]["rows"][0]["source"]["version"],
            str(self.budget.version_number),
        )
        self.assertEqual(
            rebuild_cashflow_snapshot(snapshot=snapshot, actor=self.approver),
            snapshot.result,
        )
        self.project.refresh_from_db()
        self.budget.refresh_from_db()
        self.assertEqual(
            before,
            (
                self.project.estimated_budget,
                self.project.actual_budget,
                self.budget.payload_hash,
            ),
        )
        self.assertEqual(f.eac, Decimal("100.00"))

    def test_invalid_timing_float_currency_source_and_controls_fail_closed(self):
        f = self._forecast()
        for changes in (
            {"expected_cash_on": None},
            {"expected_cash_on": "2026-10-32"},
            {"cash_amount": 0.1},
            {"cash_amount": "NaN"},
            {"currency": "USD"},
            {"cash_amount": "0"},
            {"source": {"family": "recognition_date", "id": str(uuid4())}},
            {"source": {"family": "budget_allocation", "id": str(uuid4())}},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                prepare_cashflow_supplement(
                    forecast=f,
                    actor=self.preparer,
                    rows=[self.row(**changes)],
                    controls=[],
                )
        with self.assertRaises(ValidationError):
            prepare_cashflow_supplement(
                forecast=f, actor=self.preparer, rows=[self.row()], controls=[]
            )
        self.assertFalse(ProjectCashflowSupplement.objects.exists())

    def test_unallocated_amounts_reconcile_but_expose_incomplete_coverage(self):
        rows = [
            self.row(amount="70"),
            self.row(
                key="unallocated-1",
                amount="30",
                when=None,
                state="unallocated",
                exception_reason="Cash timing evidence missing",
            ),
        ]
        _, s = self.ready(rows)
        result = self.capture(s).result
        self.assertFalse(result["complete"])
        self.assertEqual(
            len(result["exceptions"]), 2
        )  # one explicit exception in each selected plan
        self.assertEqual(result["controls"]["forecast"][0]["cash_amount"], "100")

    def test_late_reforecast_and_cancellation_preserve_baseline_and_old_snapshot(self):
        _, first = self.ready()
        old = self.capture(first)
        next_forecast = self._forecast()
        second = self.supplement(
            next_forecast, [self.row(when="2026-11-01", amount="120")]
        )
        self.approve(next_forecast)
        corrected = self.capture(first, second)
        self.assertEqual(
            corrected.result["buckets"]["2026-10-01"]["baseline"]["DISBURSEMENT"],
            "100.000001",
        )
        self.assertEqual(
            corrected.result["buckets"]["2026-11-01"]["forecast"]["DISBURSEMENT"], "120"
        )
        self.assertEqual(second.predecessor_id, first.pk)
        third_forecast = self._forecast()
        third = self.supplement(
            third_forecast,
            [
                self.row(
                    amount="120",
                    when=None,
                    state="cancelled",
                    exception_reason="Approved cancellation",
                )
            ],
        )
        self.approve(third_forecast)
        cancelled = self.capture(first, third)
        self.assertEqual(
            cancelled.result["buckets"]["2026-11-01"]["forecast"]["DISBURSEMENT"], "0"
        )
        self.assertEqual(
            rebuild_cashflow_snapshot(snapshot=old, actor=self.approver), old.result
        )
        with self.assertRaises(ValidationError):
            self.capture(first, second)
        with self.assertRaises(ValidationError):
            self.capture(first, second, knowledge_as_of=old.knowledge_as_of)

    def test_month_boundaries_horizon_timezone_and_overdue_not_rolled(self):
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save()
        _, s = self.ready(
            [
                self.row(key="before", when="2026-09-30", amount="2"),
                self.row(key="inside", when="2026-10-01", amount="3"),
                self.row(key="end", when="2026-12-01", amount="5"),
            ]
        )
        snap = self.capture(s)
        self.assertEqual(snap.timezone_name, "Asia/Tehran")
        self.assertEqual(snap.result["out_of_horizon"]["forecast"]["DISBURSEMENT"], "7")
        self.assertEqual(
            snap.result["buckets"]["2026-10-01"]["forecast"]["DISBURSEMENT"], "3"
        )
        for extra in (
            {"horizon_start": date(2026, 10, 2)},
            {"horizon_end": date(2026, 10, 1)},
            {"knowledge_as_of": timezone.now().replace(tzinfo=None)},
            {"knowledge_as_of": timezone.now() + timedelta(days=1)},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                self.capture(s, **extra)

    def test_native_treasury_event_cutoff_reversal_and_future_cash(self):
        from apps.treasury import tests as treasury
        from apps.treasury.services import reverse_posted_movement

        _, supplement = self.ready()
        self.owner = self.preparer
        self.owner_membership = self.organization.memberships.get(user=self.owner)
        self.accountant_membership = self.organization.memberships.get(
            user=self.approver
        )
        for code, parameters in treasury.ACCOUNTING_INITIAL_POLICY_PARAMETERS.items():
            if code in {
                treasury.ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
                treasury.ACCOUNTING_ROUNDING_POLICY_CODE,
            }:
                treasury.TreasuryFoundationTests._activate_policy(
                    self, code, parameters
                )
        treasury.TreasuryFoundationTests._activate_policy(
            self,
            treasury.TREASURY_SELF_APPROVAL_POLICY_CODE,
            {"allow_self_approval": True},
        )
        year = treasury.create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="CF65",
            name="Cash test year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.period = treasury.create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="Cash test period",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        cash_gl = treasury.create_account(
            organization=self.organization,
            actor=self.owner,
            code="CF1101",
            name="Cash",
            account_type="asset",
            is_posting=True,
        )
        self.clearing_gl = treasury.create_account(
            organization=self.organization,
            actor=self.owner,
            code="CF2199",
            name="Clearing",
            account_type="liability",
            is_posting=True,
        )
        bank = treasury.TreasuryFoundationTests._bank(
            self, "CFBANK", "IR0000065", cash_gl
        )

        def receipt(key, amount):
            movement = treasury.create_movement(
                organization=self.organization,
                actor=self.owner,
                kind="receipt",
                movement_date=date(2026, 10, 1),
                amount=Decimal(amount),
                description="CEP065 native test receipt",
                idempotency_key=key,
                account=bank,
                project=self.project,
            )
            return treasury.TreasuryFoundationTests._post(self, movement)

        original = receipt("native-1", "30")
        cutoff = timezone.now()
        old = self.capture(supplement, knowledge_as_of=cutoff)
        reverse_posted_movement(
            organization=self.organization,
            actor=self.owner,
            movement=original,
            requested_by=self.accountant_membership,
            accounting_date=date(2026, 10, 2),
            period=self.period,
            reason="Native reversal test",
        )
        receipt("late-backdated", "7")
        historical = self.capture(supplement, knowledge_as_of=cutoff)
        current = self.capture(supplement)
        self.assertEqual(
            historical.result["buckets"]["2026-10-01"]["actual"]["RECEIPT"], "30.000000"
        )
        self.assertEqual(
            current.result["buckets"]["2026-10-01"]["actual"]["RECEIPT"], "7.000000"
        )
        self.assertEqual(current.manifest["actual"]["controls"]["row_count"], 3)
        self.assertEqual(
            rebuild_cashflow_snapshot(snapshot=old, actor=self.approver), old.result
        )

    def test_overlap_duplicates_and_unknown_source_cannot_be_approved(self):
        f = self._forecast()
        with self.assertRaises(ValidationError):
            self.supplement(f, [self.row(), self.row()])
        with self.assertRaises(ValidationError):
            self.supplement(
                f,
                [
                    self.row(),
                    self.row(
                        key="another", source={"family": "forecast", "id": str(f.pk)}
                    ),
                ],
            )

    def test_native_commitment_and_forecast_sources_preserve_identity_not_cash_formula(
        self,
    ):
        from apps.projects import test_p4_integrated_cost as cost

        contract = cost.IntegratedProjectCostTests._contract(self, "commitment")
        fact = cost.IntegratedProjectCostTests._fact(
            self, contract, "commitment_authorized", "600.00", "CF65-COMMIT"
        )
        f = self._forecast()
        row = self.row(
            amount="17",
            source={"family": "commitment", "id": str(fact.pk)},
            economic_event_id=fact.economic_event_id,
        )
        supplement = self.supplement(
            f,
            [
                row,
                self.row(
                    key="assumption",
                    economic_event_id="uncommitted-cash-1",
                    amount="9",
                    source={"family": "forecast", "id": str(f.pk)},
                ),
            ],
        )
        self.assertEqual(
            supplement.manifest["rows"][0]["source"]["evidence"]["amount"], "600.00"
        )
        self.assertEqual(supplement.manifest["rows"][0]["cash_amount"], "17")
        self.assertEqual(supplement.manifest["rows"][1]["cash_amount"], "9")
        with self.assertRaises(ValidationError):
            self.supplement(
                self._forecast(),
                [
                    self.row(
                        source={"family": "commitment", "id": str(fact.pk)},
                        economic_event_id="invented-event",
                    )
                ],
            )

    def test_native_commercial_terms_are_evidence_without_automatic_payment_timing(
        self,
    ):
        from apps.contracts.services import (
            approve_contract_term_version,
            create_contract,
            create_contract_term_version,
        )

        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract_number="CF65",
            title="Commercial evidence",
            counterparty_name="Test party",
            direction="receivable",
            contract_type="client",
        )
        terms = create_contract_term_version(
            organization=self.organization,
            actor=self.preparer,
            contract=contract,
            effective_from=date(2026, 1, 1),
            payment_due_days=45,
            reason="Explicit commercial test terms",
        )
        f = self._forecast()
        row = self.row(
            source={"family": "contract_terms", "id": str(terms.pk)},
            direction="RECEIPT",
            amount="250",
            when="2026-11-03",
        )
        with self.assertRaises(ValidationError):
            self.supplement(f, [row])
        approve_contract_term_version(
            organization=self.organization,
            actor=self.approver,
            term_version=terms,
            reason="Independent commercial approval",
        )
        supplement = self.supplement(f, [row])
        self.assertEqual(
            supplement.manifest["rows"][0]["expected_cash_on"], "2026-11-03"
        )
        self.assertEqual(
            supplement.manifest["rows"][0]["source"]["evidence"]["payment_due_days"], 45
        )

    def test_late_attachment_queryset_update_delete_and_snapshot_corruption_denied(
        self,
    ):
        f, s = self.ready()
        with self.assertRaises(PermissionDenied):
            self.supplement(f)
        for operation in (
            lambda: ProjectCashflowSupplement.objects.filter(pk=s.pk).update(
                manifest={}
            ),
            lambda: ProjectCashflowSupplement.objects.filter(pk=s.pk).delete(),
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                operation()
        snap = self.capture(s)
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProjectCashflowSnapshot.objects.filter(pk=snap.pk).update(result={})
        snap.result = {}
        with self.assertRaises(ValidationError):
            snap.save()
        with self.assertRaises(ValidationError):
            s.delete()

    def test_cross_tenant_source_read_and_inactive_membership_are_denied(self):
        f = self._forecast()
        with self.assertRaises(PermissionDenied):
            prepare_cashflow_supplement(
                forecast=f, actor=self.outsider, rows=[], controls=[]
            )
        _, s = self.ready()
        with self.assertRaises(PermissionDenied):
            rebuild_cashflow_snapshot(snapshot=self.capture(s), actor=self.outsider)
        self.organization.memberships.filter(user=self.approver).update(
            status="suspended"
        )
        with self.assertRaises(PermissionDenied):
            self.capture(s)

    def test_retry_is_exact_and_rebuild_ignores_current_source_pointers(self):
        _, s = self.ready()
        cutoff = timezone.now()
        first = self.capture(s, knowledge_as_of=cutoff, idempotency_key="same-capture")
        self.assertEqual(
            self.capture(s, knowledge_as_of=cutoff, idempotency_key="same-capture").pk,
            first.pk,
        )
        with self.assertRaises(ValidationError):
            self.capture(
                s,
                knowledge_as_of=cutoff,
                idempotency_key="same-capture",
                horizon_end=date(2027, 1, 1),
            )
        with patch(
            "apps.projects.cashflow._source",
            side_effect=AssertionError("Current source read during rebuild"),
        ):
            self.assertEqual(
                rebuild_cashflow_snapshot(snapshot=first, actor=self.approver),
                first.result,
            )
        damaged = deepcopy(first.manifest)
        del damaged["forecast"]
        self.assertNotEqual(digest(damaged), digest(first.manifest))
        self.assertEqual(render_manifest(first.manifest), first.result)

    def test_unapproved_forecast_and_postcutoff_approval_are_not_comparable(self):
        self.workflow = self._workflow()
        f = self._forecast()
        s = self.supplement(f)
        before = timezone.now()
        with self.assertRaises(ValidationError):
            self.capture(s)
        self.approve(f)
        with self.assertRaises(ValidationError):
            self.capture(s, knowledge_as_of=before)
        self.assertEqual(
            ProjectForecastTransition.objects.filter(
                review__forecast=f, new_status="approved"
            ).count(),
            1,
        )

    def test_draft_schedule_reference_requires_explicit_cash_timing(self):
        from apps.projects.services import (
            add_project_schedule_item,
            create_project_schedule_revision,
        )

        schedule = create_project_schedule_revision(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            occurrence_id="CF65-SCHEDULE",
            data_date=date(2026, 10, 1),
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 12, 1),
            calendar_reference="Evidence only calendar",
            assumptions="No schedule acceptance",
        )
        item = add_project_schedule_item(
            schedule=schedule,
            actor=self.preparer,
            code="M1",
            name="Evidence milestone",
            planned_start=date(2026, 10, 15),
            planned_finish=date(2026, 10, 15),
            source_reference="Milestone evidence v1",
            is_milestone=True,
        )
        _, supplement = self.ready(
            [self.row(when="2026-11-03", schedule_item_id=str(item.pk))]
        )
        retained = self.capture(supplement).manifest["forecast"]["rows"][0]
        self.assertEqual(retained["expected_cash_on"], "2026-11-03")
        self.assertEqual(retained["schedule"]["planned_start"], "2026-10-15")
        self.assertEqual(len(retained["schedule"]["item_hash"]), 64)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, "draft")

    def test_cash_control_and_bucket_aggregation_preserve_all_decimal_digits(self):
        self.workflow = self._workflow()
        forecast = self._forecast()
        rows = [
            self.row(key="large", amount="12345678901234567890123456789.123456"),
            self.row(key="small", amount="0.000001"),
        ]
        source_group = "budget_allocation:" + rows[0]["source"]["id"]
        supplement = prepare_cashflow_supplement(
            forecast=forecast,
            actor=self.preparer,
            rows=rows,
            controls=[
                {
                    "source_group": source_group,
                    "direction": "DISBURSEMENT",
                    "currency": "IRR",
                    "row_count": 2,
                    "cash_amount": "12345678901234567890123456789.123457",
                }
            ],
        )
        self.approve(forecast)
        result = self.capture(supplement).result
        self.assertEqual(
            result["buckets"]["2026-10-01"]["forecast"]["DISBURSEMENT"],
            "12345678901234567890123456789.123457",
        )

    def test_current_tenant_state_and_missing_historical_settings_fail_closed(self):
        from apps.organizations.models import Organization, OrganizationSettings

        _, supplement = self.ready()
        saved = self.capture(supplement)
        cutoff = timezone.now()
        OrganizationSettings.objects.filter(organization=self.organization).update(
            updated_at=cutoff + timedelta(seconds=1)
        )
        with self.assertRaisesMessage(ValidationError, "history is unavailable"):
            self.capture(supplement, knowledge_as_of=cutoff)
        self.assertEqual(
            rebuild_cashflow_snapshot(snapshot=saved, actor=self.approver), saved.result
        )
        Organization.objects.filter(pk=self.organization.pk).update(status="suspended")
        self.assertEqual(
            self.organization.status, "active"
        )  # Stale client object cannot authorize capture.
        with self.assertRaises(PermissionDenied):
            self.capture(supplement)

    def test_changed_cash_source_blocks_approval_but_allows_rejection(self):
        self.workflow = self._workflow()
        forecast = self._forecast()
        self.supplement(forecast)
        instance = submit_project_cost_forecast(
            forecast=forecast,
            actor=self.preparer,
            workflow_version=self.workflow,
            reason="Review explicit source evidence",
            idempotency_key=forecast_submission_key(forecast),
        )
        item = instance.work_items.get()
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim-stale-cash",
        )
        with patch(
            "apps.projects.cashflow._source",
            side_effect=ValidationError("Source changed"),
        ):
            with self.assertRaises(ValidationError):
                complete_work_item(
                    actor=self.approver,
                    organization=self.organization,
                    work_item_id=item.pk,
                    outcome="approved",
                    idempotency_key="stale-cash-approve",
                    command_context={"reason": "Cannot approve stale source"},
                )
            complete_work_item(
                actor=self.approver,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="rejected",
                idempotency_key="stale-cash-reject",
                command_context={"reason": "Reject stale source evidence"},
            )
        forecast.review.refresh_from_db()
        self.assertEqual(forecast.review.status, "rejected")

    def test_database_rejects_late_bulk_insert_and_source_permission_is_rechecked(self):
        from apps.organizations.models import BusinessPermission, OrganizationRole
        from apps.organizations.models import BusinessPermissionCode as P

        _, supplement = self.ready()
        next_forecast = self._forecast()
        self.approve(next_forecast)
        with (
            self.assertRaisesMessage(DatabaseError, "cash supplement requires"),
            transaction.atomic(),
        ):
            ProjectCashflowSupplement.objects.bulk_create(
                [
                    ProjectCashflowSupplement(
                        organization=self.organization,
                        project=self.project,
                        forecast=next_forecast,
                        created_by=self.preparer,
                        payload_hash="a" * 64,
                        manifest={"late": True},
                    )
                ]
            )
        role = OrganizationRole.objects.get(
            code="company_owner", organization__isnull=True
        )
        role.permissions.remove(BusinessPermission.objects.get(code=P.BUDGETS_VIEW))
        with self.assertRaises(PermissionDenied):
            self.capture(supplement)


class CashflowAdapterTests(TestCase):
    """Unit contracts for approved owner records; real AP evidence retains scope."""

    setUp = fixtures.ForecastGovernanceTests.setUp
    _draft = fixtures.ForecastGovernanceTests._draft
    _classify_and_submit = fixtures.ForecastGovernanceTests._classify_and_submit
    _forecast = fixtures.ForecastGovernanceTests._forecast

    def test_billing_owner_fields_and_invalid_states_fail_closed(self):
        from apps.billing.models import PayableCertificate, ProgressClaim
        from apps.contracts.models import Contract, ContractTermVersion
        from apps.projects.cashflow import _source

        forecast = self._forecast()
        for family, model in (
            ("billing_claim", ProgressClaim),
            ("billing_certificate", PayableCertificate),
        ):
            # Resolve a typed owner-record snapshot: approval lifecycles belong to Billing.
            contract = Contract(
                id=uuid4(), organization=self.organization, project=self.project
            )
            terms = ContractTermVersion(
                id=uuid4(), organization=self.organization, contract=contract
            )
            source = model(
                id=uuid4(),
                organization=self.organization,
                project=self.project,
                status="approved",
                revision_number=2,
                currency_code="IRR",
                net_amount=Decimal("123.4567"),
                approved_at=timezone.now(),
                created_at=timezone.now(),
                contract=contract,
                contract_term_version=terms,
                calculation_snapshot={"source_version": 2},
                due_date=date(2026, 11, 7),
            )
            with patch.object(model.objects, "select_for_update") as query:
                query.return_value.get.return_value = source
                resolved = _source(
                    reference={"family": family, "id": str(source.pk)},
                    forecast=forecast,
                    actor=self.preparer,
                )
                query.return_value.get.assert_called_with(
                    pk=str(source.pk), organization_id=self.organization.pk
                )
                self.assertEqual(resolved["version"], "2")
                self.assertEqual(resolved["evidence"]["net_amount"], "123.4567")
                for field, bad in (
                    ("status", "draft"),
                    ("currency_code", "USD"),
                    ("project_id", uuid4()),
                    ("approved_at", None),
                ):
                    previous = getattr(source, field)
                    setattr(source, field, bad)
                    with self.assertRaises(ValidationError):
                        _source(
                            reference={"family": family, "id": str(source.pk)},
                            forecast=forecast,
                            actor=self.preparer,
                        )
                    setattr(source, field, previous)

    def test_persisted_apar_owner_evidence_without_invented_posting(self):
        from apps.projects.cashflow import _source
        from apps.subledgers.models import Obligation

        forecast = self._forecast()
        source_id = uuid4()
        obligation = Obligation.objects.create(
            organization=self.organization,
            project=self.project,
            direction="receivable",
            source_kind="test.exact-source.v1",
            source_uuid=source_id,
            source_version=1,
            source_status="final",
            source_hash="a" * 64,
            source_snapshot={"source": str(source_id)},
            party_name_snapshot="CEP065 test source",
            original_amount=Decimal(100),
            recognized_on=date(2026, 10, 1),
            due_date=date(2026, 11, 1),
            idempotency_key=str(source_id),
            payload_hash="b" * 64,
            recognized_by=self.organization.memberships.get(user=self.preparer),
        )
        resolved = _source(
            reference={"family": "obligation", "id": str(obligation.pk)},
            forecast=forecast,
            actor=self.preparer,
        )
        self.assertEqual(resolved["evidence"]["original_amount"], "100.000000")
        self.assertEqual(resolved["evidence"]["journal_id"], "")
