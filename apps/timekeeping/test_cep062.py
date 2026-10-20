"""Synthetic approved bindings; native targets, no actual Mission policy activation."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.expenses.models import PlatformExpenseGroup
from apps.organizations.models import (
    BusinessPermission,
    Organization,
)
from apps.payroll import test_p7_s29_s32_financial_handoffs as fixtures
from apps.payroll.models import PayrollAdjustment
from apps.payroll.services import create_run
from apps.projects.models import Project, ProjectCostFact
from apps.subledgers.models import Obligation
from apps.treasury.models import PaymentRequest, TreasuryMovement
from tests.retirement_fixtures import explicit_fixture_roles

from . import mission_routing as api
from .mission_models import MissionEffect, MissionEffectEvent
from .models import LeaveMissionRequest
from .services import (
    create_leave_mission_request,
    review_time_request,
    submit_time_request,
)


class MissionRoutingFixture:
    _member = fixtures.PayrollFinancialHandoffTests._member
    _monetary_versions = fixtures.PayrollFinancialHandoffTests._monetary_versions

    def setUp(self):
        fixtures.PayrollFinancialHandoffTests.setUp(self)
        for user in (self.owner, self.reviewer):
            self.organization.memberships.get(
                user=user
            ).role_definition.permissions.add(*BusinessPermission.objects.all())
        explicit_fixture_roles(self.organization)
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "Other synthetic fixture"}
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="MISSION",
            name="Synthetic Mission",
            created_by=self.owner,
        )
        self.mission = create_leave_mission_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            kind="mission",
            category_code="synthetic-category",
            starts_at=timezone.now() + timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=9),
            reason="Synthetic approved request",
            policy_reference="SYNTHETIC-EXT0016-NOT-ACTIVATION",
        )
        submit_time_request(
            organization=self.organization, actor=self.owner, request=self.mission
        )
        review_time_request(
            organization=self.organization,
            actor=self.reviewer,
            request=self.mission,
            approve=True,
            reason="Independent synthetic source approval",
        )
        self.mission.refresh_from_db()
        self.adjustment_run = create_run(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            code="MISSION-ADJUST",
            idempotency_key="mission-adjust",
            employees=[self.employee],
            kind="off_cycle",
        )
        self.payroll_target = api.PayrollTarget(
            self.adjustment_run,
            self.component,
            "off_cycle",
            self.mission.starts_at.date(),
        )
        self.specs = (
            api.EffectSpec(
                uuid4(),
                "synthetic-payroll",
                "payroll",
                Decimal("50.00"),
                "IRR",
                self.payroll_target,
            ),
            api.EffectSpec(
                uuid4(),
                "synthetic-direct",
                "expense",
                Decimal("30.00"),
                "IRR",
                api.ExpenseTarget(
                    "other",
                    self.mission.starts_at.date(),
                    "Synthetic approved direct reimbursement",
                ),
            ),
            api.EffectSpec(
                uuid4(),
                "synthetic-advance",
                "treasury",
                Decimal("20.00"),
                "IRR",
                api.TreasuryTarget("Synthetic approved mission advance"),
            ),
        )
        self.plan = api.MissionPlan(
            "approved-synthetic-v1",
            "Synthetic approved effect mapping, no real policy activation",
            self.specs,
        )
        self.binding = api.MissionPolicyBinding(
            lambda **kw: self.plan,
            lambda **kw: replace(self.payroll_target, kind="correction"),
        )
        self.policies = patch.object(
            api,
            "POLICIES",
            {(str(self.organization.pk), self.mission.policy_reference): self.binding},
        )
        self.policies.start()
        self.addCleanup(self.policies.stop)

    def route(self, index=0, **kwargs):
        spec = self.specs[index]
        arguments = {
            "organization": self.organization,
            "actor": self.owner,
            "mission_id": self.mission.pk,
            "effect_id": spec.effect_id,
            "effect_type": spec.effect_type,
            "reason": "Synthetic approved routing",
        }
        arguments.update(kwargs)
        return api.route_mission_effect(**arguments)

    def resolve(self, effect, **kwargs):
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "effect_id": effect.pk,
            "reason": "Synthetic explicit cancellation",
        }
        args.update(kwargs)
        return api.resolve_mission_effect(**args)

    def read(self):
        return api.reconcile_mission_effects(
            organization=self.organization, actor=self.owner, mission_id=self.mission.pk
        )


class MissionRoutingTests(MissionRoutingFixture, TestCase):
    def test_three_independent_effects_have_exactly_one_native_route_each(self):
        before = [
            m.objects.count()
            for m in (JournalEntry, TreasuryMovement, Obligation, ProjectCostFact)
        ]
        effects = [self.route(i) for i in range(3)]
        for i, effect in enumerate(effects):
            self.assertEqual(effect.pk, self.route(i).pk)
            self.assertEqual(
                sum(
                    bool(x)
                    for x in (
                        effect.payroll_target_id,
                        effect.expense_target_id,
                        effect.treasury_target_id,
                    )
                ),
                1,
            )
            self.assertEqual(effect.mission_version, self.plan.mission_version)
        self.assertEqual(
            before,
            [
                m.objects.count()
                for m in (JournalEntry, TreasuryMovement, Obligation, ProjectCostFact)
            ],
        )
        self.assertEqual(effects[1].expense_target.status, "draft")
        self.assertEqual(effects[2].treasury_target.kind, "employee_advance")
        self.assertEqual(self.mission.state, "approved")
        result = self.read()
        self.assertTrue(all(x["source_matches"] for x in result["rows"]))
        Path("docs/governance/cep/evidence/CEP-062_INTEGRATION_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic_policy_only": True,
                    "actual_activation": False,
                    "result": result,
                    "source_state": self.mission.state,
                    "native_financial_counts_before": before,
                    "native_financial_counts_after": [
                        m.objects.count()
                        for m in (
                            JournalEntry,
                            TreasuryMovement,
                            Obligation,
                            ProjectCostFact,
                        )
                    ],
                },
                indent=2,
            )
        )

    def test_absent_policy_is_held_despite_free_text_reference(self):
        with (
            patch.object(api, "POLICIES", {}),
            self.assertRaisesMessage(
                ValidationError, "APPROVED_MISSION_POLICY_REQUIRED"
            ),
        ):
            self.route()
        self.assertFalse(MissionEffect.objects.exists())
        self.assertEqual(
            MissionEffectEvent.objects.get().error_code,
            "APPROVED_MISSION_POLICY_REQUIRED",
        )
        self.assertEqual(
            LeaveMissionRequest.objects.get(pk=self.mission.pk).state, "approved"
        )

    def test_duplicate_or_wrong_route_classification_and_unknown_effect_are_held(self):
        for plan in (
            replace(self.plan, effects=(self.specs[0], self.specs[0])),
            replace(self.plan, effects=(replace(self.specs[0], route="treasury"),)),
        ):
            self.plan = plan
            with self.assertRaises(ValidationError):
                self.route()
        self.assertFalse(MissionEffect.objects.exists())

    def test_immutable_version_payload_mismatch_and_new_version_cannot_double_route(
        self,
    ):
        original = self.route()
        self.plan = replace(
            self.plan, effects=(replace(self.specs[0], amount=Decimal(51)),)
        )
        with self.assertRaisesMessage(
            ValidationError, "IMMUTABLE_EFFECT_PAYLOAD_MISMATCH"
        ):
            self.route()
        self.plan = replace(self.plan, mission_version="approved-v2")
        with self.assertRaisesMessage(
            ValidationError, "PRIOR_EFFECT_REQUIRES_CONTROLLED_RESOLUTION"
        ):
            self.route()
        self.assertEqual(MissionEffect.objects.count(), 1)
        self.assertEqual(
            PayrollAdjustment.objects.get(pk=original.payroll_target_id).amount,
            Decimal(50),
        )

    def test_late_target_failure_rolls_back_and_successful_retry_revalidates_source(
        self,
    ):
        count = PayrollAdjustment.objects.count()
        with (
            patch.object(
                MissionEffect.objects,
                "create",
                side_effect=ValidationError("Internal private target detail"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.route()
        self.assertEqual(PayrollAdjustment.objects.count(), count)
        failure = MissionEffectEvent.objects.get()
        self.assertEqual(failure.error_code, "TARGET_OPERATION_FAILED")
        self.assertNotIn("private", failure.error_code)
        self.assertEqual(self.route().mission_id, self.mission.pk)
        self.assertEqual(MissionEffectEvent.objects.filter(kind="created").count(), 1)

    def test_source_or_policy_drift_during_target_operation_rolls_back(self):
        original = self.binding.read_plan
        reads = []

        def drift(**kwargs):
            reads.append(True)
            plan = original(**kwargs)
            return (
                plan
                if len(reads) == 1
                else replace(plan, mission_version="changed-during-write")
            )

        with (
            patch.object(
                api,
                "POLICIES",
                {
                    (
                        str(self.organization.pk),
                        self.mission.policy_reference,
                    ): api.MissionPolicyBinding(drift)
                },
            ),
            self.assertRaisesMessage(
                ValidationError, "APPROVED_SOURCE_CHANGED_DURING_TARGET_OPERATION"
            ),
        ):
            self.route()
        self.assertFalse(MissionEffect.objects.exists())
        self.assertFalse(PayrollAdjustment.objects.exists())

    def test_native_permissions_tenant_and_source_approval_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            self.route(actor=self.denied)
        other = Organization.objects.create(
            name="Foreign", slug="foreign-mission", created_by=self.owner
        )
        with self.assertRaises(PermissionDenied):
            self.route(organization=other)
        LeaveMissionRequest.objects.filter(pk=self.mission.pk).update(state="rejected")
        with self.assertRaisesMessage(
            ValidationError, "APPROVED_INDEPENDENT_MISSION_REQUIRED"
        ):
            self.route()
        self.assertFalse(MissionEffect.objects.exists())

    def test_native_target_permissions_remain_independent_of_mission_review(self):
        from apps.organizations.models import BusinessPermissionCode as P

        membership = self.organization.memberships.get(user=self.actor)
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=P.LEAVE_MISSION_REVIEW)
        )
        for index in range(3):
            with (
                self.subTest(route=self.specs[index].route),
                self.assertRaises(PermissionDenied),
            ):
                self.route(index, actor=self.actor)
        self.assertFalse(MissionEffect.objects.exists())
        self.assertEqual(MissionEffectEvent.objects.filter(kind="failed").count(), 3)

    def test_missing_approval_metadata_and_foreign_target_context_are_held(self):
        from apps.payroll.models import PayrollComponent

        approved_time = self.mission.reviewed_at
        LeaveMissionRequest.objects.filter(pk=self.mission.pk).update(reviewed_at=None)
        with self.assertRaisesMessage(
            ValidationError, "APPROVED_INDEPENDENT_MISSION_REQUIRED"
        ):
            self.route()
        LeaveMissionRequest.objects.filter(pk=self.mission.pk).update(
            reviewed_at=approved_time
        )
        other = Organization.objects.create(
            name="Foreign target", slug="foreign-native-target", created_by=self.owner
        )
        component = PayrollComponent.objects.create(
            organization=other,
            code="FOREIGN",
            name="Foreign component",
            kind="earning",
            net_effect="add",
            created_by=self.owner,
        )
        self.plan = replace(
            self.plan,
            effects=(
                replace(
                    self.specs[0],
                    target=replace(self.payroll_target, component=component),
                ),
            ),
        )
        with self.assertRaises(ValidationError):
            self.route()
        self.assertFalse(MissionEffect.objects.exists())

    def test_payroll_correction_is_exact_inverse_with_retained_source_and_replacement(
        self,
    ):
        original = self.route()
        self.plan = replace(
            self.plan,
            mission_version="approved-v2",
            effects=(replace(self.specs[0], amount=Decimal("65.00")),),
        )
        event = self.resolve(
            original, replace=True, reason="Explicit approved correction"
        )
        self.assertEqual(event.payroll_inverse.amount, Decimal(-50))
        self.assertEqual(event.replacement.amount, Decimal(65))
        self.assertEqual(
            self.resolve(
                original, replace=True, reason="Explicit approved correction"
            ).pk,
            event.pk,
        )
        self.assertEqual(MissionEffect.objects.count(), 2)
        rows = self.read()["rows"]
        self.assertEqual({x["state"] for x in rows}, {"replaced", "active"})
        self.assertEqual(
            LeaveMissionRequest.objects.get(pk=self.mission.pk).state, "approved"
        )
        Path("docs/governance/cep/evidence/CEP-062_CORRECTION_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "native_payroll_inverse": str(event.payroll_inverse_id),
                    "inverse_amount": str(event.payroll_inverse.amount),
                    "inverse_run_status": event.payroll_inverse.run.status,
                    "source_state": "approved",
                    "reconciliation": self.read(),
                    "cash_or_gl_mutation": False,
                },
                indent=2,
            )
        )

    def test_expense_cancel_and_replacement_use_native_void_history(self):
        original = self.route(1)
        self.plan = replace(
            self.plan,
            mission_version="expense-correction-v2",
            effects=(replace(self.specs[1], amount=Decimal(25)),),
        )
        event = self.resolve(original, replace=True)
        original.expense_target.refresh_from_db()
        self.assertEqual(original.expense_target.status, "void")
        self.assertEqual(
            event.replacement.expense_target.replaces_id, original.expense_target_id
        )
        self.assertEqual(event.replacement.expense_target.source_version, 2)

    def test_unpaid_advance_cancel_is_native_and_never_employee_loan(self):
        original = self.route(2)
        event = self.resolve(original)
        original.treasury_target.refresh_from_db()
        self.assertEqual(original.treasury_target.status, "cancelled")
        self.assertIsNone(event.treasury_reversal_id)
        self.assertFalse(TreasuryMovement.objects.exists())
        self.assertEqual(original.treasury_target.kind, "employee_advance")

    def test_cancel_failure_retains_active_original_and_rolls_back_inverse(self):
        original = self.route()
        count = PayrollAdjustment.objects.count()
        create_event = MissionEffectEvent.objects.create

        def fail_terminal(**kwargs):
            if kwargs.get("kind") in {"cancelled", "replaced"}:
                raise ValidationError("Late correction failure")
            return create_event(**kwargs)

        with (
            patch.object(
                MissionEffectEvent.objects, "create", side_effect=fail_terminal
            ),
            self.assertRaises(ValidationError),
        ):
            self.resolve(original)
        self.assertEqual(PayrollAdjustment.objects.count(), count)
        self.assertFalse(
            original.events.filter(kind__in=("cancelled", "replaced")).exists()
        )

    def test_finalized_payroll_never_uses_unconsumed_inverse_for_replacement(self):
        from apps.payroll.models import PayrollRun

        original = self.route()
        # Inject a finalized marker only to exercise the fail-closed boundary;
        # this does not claim native Payroll finalization/activation evidence.
        PayrollRun.objects.filter(pk=self.adjustment_run.pk).update(status="finalized")
        self.plan = replace(self.plan, mission_version="approved-v2")
        before = PayrollAdjustment.objects.count()
        with self.assertRaisesMessage(
            ValidationError, "FINALIZED_NATIVE_PAYROLL_INVERSE_REQUIRED"
        ):
            self.resolve(original, replace=True)
        self.assertEqual(PayrollAdjustment.objects.count(), before)
        self.assertEqual(MissionEffect.objects.count(), 1)
        self.assertFalse(original.events.filter(kind="replaced").exists())

    def test_finalized_native_inverse_reference_is_consumed_without_reversing_run(self):
        from apps.payroll.models import PayrollRun, PayrollRunEmployee
        from apps.payroll.services import record_adjustment

        original = self.route()
        # Sealed synthetic producer fixtures, as in the retained Payroll source
        # fixture. These markers do not certify Payroll calculation/finalization.
        PayrollRun.objects.filter(pk=self.adjustment_run.pk).update(status="finalized")
        PayrollRunEmployee.objects.filter(run=self.adjustment_run).update(
            status="finalized"
        )
        original_result = self.adjustment_run.employee_results.get(
            employee=self.employee
        )
        inverse_run = create_run(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            code="MISSION-INV",
            idempotency_key="mission-inverse-run",
            employees=[self.employee],
            kind="adjustment",
        )
        inverse = record_adjustment(
            organization=self.organization,
            actor=self.owner,
            run=inverse_run,
            employee=self.employee,
            component=self.component,
            kind="correction",
            amount=-original.amount,
            effective_on=self.mission.starts_at.date(),
            source_reference="mission-reverse:" + original.identity_hash,
            reason="Explicit synthetic native inverse",
            original_result=original_result,
            source_payload={"reverses_mission_effect": original.identity_hash},
        )
        PayrollRun.objects.filter(pk=inverse_run.pk).update(status="finalized")
        successor = create_run(
            organization=self.organization,
            actor=self.owner,
            period=self.period,
            code="MISSION-RPL",
            idempotency_key="mission-replacement-run",
            employees=[self.employee],
            kind="adjustment",
        )
        self.plan = replace(
            self.plan,
            mission_version="approved-v2",
            effects=(
                replace(
                    self.specs[0],
                    target=replace(
                        self.payroll_target,
                        run=successor,
                        original_result=original_result,
                    ),
                ),
            ),
        )
        binding = api.MissionPolicyBinding(lambda **kw: self.plan, lambda **kw: inverse)
        before = PayrollAdjustment.objects.count()
        with patch.object(
            api,
            "POLICIES",
            {(str(self.organization.pk), self.mission.policy_reference): binding},
        ):
            event = self.resolve(original, replace=True)
        self.assertEqual(event.payroll_inverse_id, inverse.pk)
        self.assertEqual(PayrollAdjustment.objects.count(), before + 1)
        self.assertEqual(
            PayrollRun.objects.get(pk=self.adjustment_run.pk).status, "finalized"
        )
        self.assertEqual(event.replacement.payroll_target.run_id, successor.pk)

    def test_read_only_reconciliation_exposes_native_target_drift(self):
        effect = self.route(2)
        self.assertTrue(self.read()["rows"][0]["target_matches"])
        # Inject mutable target drift only in this disposable synthetic fixture.
        PaymentRequest.objects.filter(pk=effect.treasury_target_id).update(
            amount=Decimal(99)
        )
        count = MissionEffect.objects.count()
        row = self.read()["rows"][0]
        self.assertFalse(row["target_matches"])
        self.assertEqual(row["state"], "target_drift")
        self.assertEqual(MissionEffect.objects.count(), count)
        with self.assertRaisesMessage(
            ValidationError, "NATIVE_TARGET_LINEAGE_MISMATCH"
        ):
            self.route(2)

    def test_issued_advance_requires_native_treasury_reversal_before_resolution(self):
        from apps.organizations.models import PlatformPolicy
        from apps.treasury.services import (
            create_movement,
            decide_payment_request,
            open_advance,
            release_payment_request,
            reverse_advance_issue,
            submit_payment_request,
        )
        from tests.retirement_fixtures import CashFixture

        activate = CashFixture._activate_policy

        def missing_only(cash, code, parameters):
            if not PlatformPolicy.objects.filter(code=code).exists():
                activate(cash, code, parameters)

        with patch.object(CashFixture, "_activate_policy", missing_only):
            cash = CashFixture(organization=self.organization, owner=self.owner)
        explicit_fixture_roles(self.organization)
        effect = self.route(2)
        request = effect.treasury_target
        submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="Synthetic submit",
        )
        decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            approve=True,
            reason="Synthetic approval",
        )
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="disbursement",
            movement_date=self.mission.starts_at.date(),
            amount=effect.amount,
            description="Synthetic approved advance",
            idempotency_key="mission-cash",
            account=cash.bank,
            project=self.project,
        )
        cash.post(movement)
        movement.refresh_from_db()
        release_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            movement=movement,
            reason="Synthetic issue",
        )
        request.refresh_from_db()
        with self.assertRaisesMessage(
            ValidationError, "NATIVE_TREASURY_ADVANCE_REVERSAL_REQUIRED"
        ):
            self.resolve(effect)
        advance = open_advance(
            organization=self.organization, actor=self.owner, request=request
        )
        reverse_advance_issue(
            organization=self.organization,
            actor=self.owner,
            advance=advance,
            requested_by=self.organization.memberships.get(user=self.reviewer),
            accounting_date=self.mission.starts_at.date(),
            period=cash.period,
            reason="Native Treasury correction",
        )
        event = self.resolve(effect)
        self.assertEqual(event.treasury_reversal.reverses_id, movement.pk)
        self.assertEqual(event.treasury_reversal.status, "posted")
        self.assertEqual(event.kind, "cancelled")
        Path("docs/governance/cep/evidence/CEP-062_ADVANCE_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "native_advance": str(advance.pk),
                    "original_cash": str(movement.pk),
                    "native_reversal": str(event.treasury_reversal_id),
                    "routing_consumed_existing_native_reversal": True,
                    "reconciliation": self.read(),
                },
                indent=2,
            )
        )

    def test_database_identity_constraints_and_orm_immutability(self):
        effect = self.route()
        for operation in (
            lambda: MissionEffect.objects.filter(pk=effect.pk).update(route="treasury"),
            lambda: MissionEffect.objects.filter(pk=effect.pk).delete(),
            lambda: MissionEffectEvent.objects.all().delete(),
        ):
            with self.assertRaises(ValidationError):
                operation()
        with (
            self.assertRaises(IntegrityError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE timekeeping_missioneffect SET route='treasury' WHERE id=%s",
                [effect.pk],
            )
        effect.amount = Decimal(999)
        with self.assertRaises(ValidationError):
            effect.save()
        with transaction.atomic(), self.assertRaises(ValidationError):
            MissionEffect.objects.create(
                organization=self.organization,
                mission=self.mission,
                mission_version=effect.mission_version,
                effect_id=effect.effect_id,
                effect_type=effect.effect_type,
                route=effect.route,
                identity_hash=effect.identity_hash,
                payload_hash=effect.payload_hash,
                source_snapshot=effect.source_snapshot,
                policy_reference=effect.policy_reference,
                amount=Decimal(50),
                currency="IRR",
                payroll_target=effect.payroll_target,
                recorded_by=self.owner,
            )


class MissionRoutingConcurrencyTests(MissionRoutingFixture, TransactionTestCase):
    def test_duplicate_source_race_has_one_native_target(self):
        from apps.accounts.models import User

        def worker(_):
            close_old_connections()
            try:
                return api.route_mission_effect(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    mission_id=self.mission.pk,
                    effect_id=self.specs[0].effect_id,
                    effect_type=self.specs[0].effect_type,
                    reason="Synthetic duplicate race",
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            identities = list(pool.map(worker, range(2)))
        self.assertEqual(len(set(identities)), 1)
        self.assertEqual(MissionEffect.objects.count(), 1)
        self.assertEqual(PayrollAdjustment.objects.count(), 1)
