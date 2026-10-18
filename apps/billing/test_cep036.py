"""Synthetic code adapter fixtures only; no official formula or activation."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.contracts.models import Contract, ContractDirection, ContractStatus
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipRole,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
    OrganizationStatus,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.projects.services import create_project

from . import indexation as service
from .models import IndexationCalculation, IndexationRuleVersion, ProgressClaim


class IndexationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="idx-owner")
        self.organization = Organization.objects.create(name="IDX", slug="idx")
        role = OrganizationRole.objects.create(
            code="idx-test", name="Synthetic operator"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    P.PROJECTS_CREATE,
                    P.CONTRACT_TERMS_MANAGE,
                    P.INDEXATION_RULES_MANAGE,
                    P.INDEXATION_CALCULATE,
                    P.INDEXATION_CORRECT,
                ]
            )
        )
        self.membership = self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status="active",
            role_definition=role,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Synthetic fixture",
        )
        self.project = create_project(
            organization=self.organization, actor=self.owner, code="IDX", name="IDX"
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="IDX",
            title="Synthetic",
            counterparty_name="Synthetic",
            direction=ContractDirection.RECEIVABLE,
            status=ContractStatus.ACTIVE,
            contract_value=Decimal(100),
        )
        self.context = {
            "actor": self.owner,
            "organization": self.organization,
            "contract": self.contract,
        }
        self.specification = {k: "SYNTHETIC-" + k for k in service.SPECIFICATION_FIELDS}
        self.inputs = {
            "base_period": "synthetic-base",
            "current_period": "synthetic-current",
            "indexes": {
                "base": {
                    "source_reference": "SYNTHETIC-SOURCE",
                    "source_version": "fixture-1",
                    "evidence_reference": "SYNTHETIC-EVIDENCE",
                    "period": "synthetic-base",
                    "value": "100.00",
                }
            },
            "values": {"amount": "12.34567890"},
        }
        self.rule = self.stage()
        self.registry = patch.dict(service.ADAPTERS, {}, clear=True)
        self.registry.start()
        self.addCleanup(self.registry.stop)
        service.register_adapter(
            "synthetic", service.IndexationAdapter(self.receipt, self.result)
        )

    def stage(self, **changes):
        data = dict(
            self.context,
            code="SYNTHETIC",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            adapter_key="synthetic",
            specification=deepcopy(self.specification),
            reason="Synthetic staging",
        )
        return service.stage_rule(**(data | changes))

    def receipt(self, request):
        return service.ApprovalReceipt(
            request["rule_sha256"],
            service.digest(request),
            service.digest(request["inputs"]["indexes"]),
            "SYNTHETIC-APPROVAL",
            "SYNTHETIC-EVIDENCE",
            "test-v1",
        )

    def result(self, request):
        # Test-only values; reversal is deliberately not a generic negative amount.
        return {
            "calculate": Decimal("12.34567890"),
            "correct": Decimal(15),
            "reverse": Decimal(0),
        }[request["operation"]]

    def calculate(self, **changes):
        data = dict(
            self.context,
            rule=self.rule,
            calculation_date=date(2026, 6, 1),
            inputs=deepcopy(self.inputs),
            idempotency_key="first",
            reason="Synthetic case",
        )
        return service.calculate(**(data | changes))

    def test_snapshot_pins_rule_source_period_evidence_approval_actor_and_decimal(self):
        record = self.calculate()
        record.refresh_from_db()
        self.assertEqual(record.snapshot["result"], "12.34567890")
        self.assertEqual(record.snapshot["request"]["inputs"], self.inputs)
        self.assertEqual(record.snapshot["request"]["rule_sha256"], self.rule.sha256)
        self.assertEqual(record.snapshot["approval"]["adapter_version"], "test-v1")
        self.assertEqual(record.actor_id, self.owner.pk)
        self.assertIsNotNone(record.created_at)
        record.full_clean()
        self.assertEqual(ProgressClaim.objects.count(), 0)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.contract_value, Decimal(100))

    def test_versioning_does_not_rewrite_calculation_or_old_rule(self):
        record = self.calculate()
        before = deepcopy(record.snapshot)
        second = self.stage(
            specification=self.specification | {"formula_reference": "SYNTHETIC-2"}
        )
        self.assertEqual(second.version, 2)
        self.assertNotEqual(second.sha256, self.rule.sha256)
        record.refresh_from_db()
        self.assertEqual(record.snapshot, before)
        self.assertEqual(record.rule_id, self.rule.pk)

    def test_missing_adapter_and_staging_never_activate(self):
        service.ADAPTERS.clear()
        with self.assertRaises(ValidationError):
            self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_missing_or_mismatched_approval_fails_closed(self):
        for field in (
            None,
            "rule_sha256",
            "request_sha256",
            "source_snapshot_sha256",
            "approval_reference",
            "evidence_reference",
            "adapter_version",
        ):

            def receipt(request, field=field):
                return (
                    None
                    if field is None
                    else replace(self.receipt(request), **{field: ""})
                )

            service.ADAPTERS["synthetic"] = service.IndexationAdapter(
                receipt, self.result
            )
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_approval_cannot_be_replayed_for_other_rule_request_or_source(self):
        for field in ("rule_sha256", "request_sha256", "source_snapshot_sha256"):

            def receipt(request, field=field):
                return replace(self.receipt(request), **{field: "0" * 64})

            service.ADAPTERS["synthetic"] = service.IndexationAdapter(
                receipt, self.result
            )
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_no_hidden_specification_defaults(self):
        for key in service.SPECIFICATION_FIELDS:
            for value in (None, "", 0, 0.1):
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(ValidationError),
                ):
                    self.stage(specification=self.specification | {key: value})
        with self.assertRaises(ValidationError):
            self.stage(specification={})
        self.assertEqual(IndexationRuleVersion.objects.count(), 1)

    def test_invalid_indexes_periods_values_and_floats_fail_before_adapter(self):
        bad = [
            self.inputs | {"base_period": ""},
            self.inputs | {"indexes": {}},
            self.inputs | {"values": {"amount": 0.1}},
            self.inputs | {"extra": "x"},
            self.inputs | {"indexes": {"x": {"value": "1"}}},
        ]
        for value in ("NaN", "Infinity", "invalid"):
            bad.append(
                self.inputs
                | {
                    "indexes": {
                        "base": self.inputs["indexes"]["base"] | {"value": value}
                    }
                }
            )
        for inputs in bad:
            with self.subTest(inputs=inputs), self.assertRaises(ValidationError):
                self.calculate(inputs=inputs)
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_effective_date_bounds_fail_closed(self):
        for when in (date(2025, 12, 31), date(2027, 1, 1)):
            with self.assertRaises(ValidationError):
                self.calculate(calculation_date=when)
        for when in (date(2026, 1, 1), date(2026, 12, 31)):
            self.calculate(calculation_date=when, idempotency_key=str(when))

    def test_decimal_result_is_required_and_never_implicitly_rounded(self):
        for result in (0.1, "1", Decimal("NaN"), Decimal("Infinity")):
            service.ADAPTERS["synthetic"] = service.IndexationAdapter(
                self.receipt, lambda r, result=result: result
            )
            with self.subTest(result=result), self.assertRaises(ValidationError):
                self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_idempotent_retry_and_collision(self):
        first = self.calculate()
        self.assertEqual(self.calculate().pk, first.pk)
        with self.assertRaises(ValidationError):
            self.calculate(reason="Different intent")
        self.assertEqual(IndexationCalculation.objects.count(), 1)

    def test_correction_and_reversal_append_history_and_prevent_forks(self):
        first = self.calculate()
        before = deepcopy(first.snapshot)
        corrected = self.calculate(
            operation="correct", prior=first, idempotency_key="correct"
        )
        reversed_record = self.calculate(
            operation="reverse", prior=corrected, idempotency_key="reverse"
        )
        self.assertEqual(reversed_record.snapshot["result"], "0")
        self.assertEqual(corrected.snapshot["request"]["prior_sha256"], first.sha256)
        self.assertEqual(reversed_record.prior_id, corrected.pk)
        first.refresh_from_db()
        self.assertEqual(first.snapshot, before)
        self.assertEqual(
            self.calculate(
                operation="correct", prior=first, idempotency_key="correct"
            ).pk,
            corrected.pk,
        )
        for prior in (first, corrected, reversed_record):
            with self.assertRaises(ValidationError):
                self.calculate(operation="reverse", prior=prior, idempotency_key="fork")

    def test_correction_requires_explicit_adapter_approval(self):
        first = self.calculate()
        service.ADAPTERS["synthetic"] = service.IndexationAdapter(
            lambda r: None, self.result
        )
        with self.assertRaises(ValidationError):
            self.calculate(operation="reverse", prior=first, idempotency_key="reverse")
        self.assertFalse(IndexationCalculation.objects.filter(prior=first).exists())

    def test_invalid_transition_shapes_fail(self):
        first = self.calculate()
        for changes in (
            {"operation": "calculate", "prior": first},
            {"operation": "correct"},
            {"operation": "reverse"},
            {"operation": "invented"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.calculate(**(changes | {"idempotency_key": "invalid"}))

    def test_rule_and_calculation_history_cannot_be_edited_deleted_or_bulk_written(
        self,
    ):
        record = self.calculate()
        for obj in (self.rule, record):
            for action in (
                obj.save,
                obj.delete,
                lambda obj=obj: (
                    type(obj).objects.filter(pk=obj.pk).update(reason="rewrite")
                ),
                lambda obj=obj: type(obj).objects.filter(pk=obj.pk).delete(),
                lambda obj=obj: type(obj).objects.bulk_create([obj]),
            ):
                with self.assertRaises(ValidationError):
                    action()

    def test_forged_snapshot_or_rule_digest_rejected_by_model(self):
        record = self.calculate()
        record.snapshot["result"] = "999"
        with self.assertRaises(ValidationError):
            record.full_clean()
        self.rule.sha256 = "0" * 64
        with self.assertRaises(ValidationError):
            self.rule.full_clean()

    def test_adapter_failure_rolls_back_without_partial_history(self):
        def fail(request):
            raise RuntimeError("synthetic failure")

        service.ADAPTERS["synthetic"] = service.IndexationAdapter(self.receipt, fail)
        with self.assertRaises(RuntimeError):
            self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)

    def test_adapter_cannot_mutate_pinned_input(self):
        def calculate(request):
            request["inputs"]["base_period"] = "mutated"
            return Decimal(1)

        service.ADAPTERS["synthetic"] = service.IndexationAdapter(
            self.receipt, calculate
        )
        self.assertEqual(self.calculate().snapshot["request"]["inputs"], self.inputs)

    def test_unregistered_and_duplicate_adapter_keys_rejected(self):
        with self.assertRaises(ValueError):
            service.register_adapter("synthetic", service.ADAPTERS["synthetic"])
        with self.assertRaises(ValueError):
            service.register_adapter("", service.ADAPTERS["synthetic"])

    def test_contract_scope_and_current_tenant_state_are_rechecked(self):
        other = Organization.objects.create(name="Other", slug="idx-other")
        with self.assertRaises(PermissionDenied):
            self.calculate(organization=other)
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save()
        with self.assertRaises(PermissionDenied):
            self.calculate()

    def test_no_membership_authority_fails_closed(self):
        outsider = User.objects.create_user(username="idx-outsider")
        with self.assertRaises(PermissionDenied):
            self.calculate(actor=outsider)

    def test_new_capabilities_are_explicit_and_never_default_granted(self):
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        codes = {
            P.INDEXATION_RULES_MANAGE,
            P.INDEXATION_CALCULATE,
            P.INDEXATION_CORRECT,
        }
        for permissions in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertFalse(codes & set(permissions))
        first = self.calculate()
        for code, action in (
            (P.INDEXATION_RULES_MANAGE, self.stage),
            (P.INDEXATION_CALCULATE, self.calculate),
            (
                P.INDEXATION_CORRECT,
                lambda: self.calculate(
                    operation="reverse", prior=first, idempotency_key="denied"
                ),
            ),
        ):
            permission = BusinessPermission.objects.get(code=code)
            self.membership.role_definition.permissions.remove(permission)
            with self.subTest(code=code), self.assertRaises(PermissionDenied):
                action()
            self.membership.role_definition.permissions.add(permission)

    def test_project_scope_does_not_expand_contract_authority(self):
        MembershipScopeGrant.objects.filter(membership=self.membership).delete()
        with self.assertRaises(PermissionDenied):
            self.calculate()

    def test_other_contract_rule_and_prior_cannot_be_used(self):
        other_contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="IDX2",
            title="Other",
            counterparty_name="Synthetic",
            contract_value=Decimal(100),
        )
        other_rule = self.stage(contract=other_contract)
        first = self.calculate()
        with self.assertRaises(PermissionDenied):
            self.calculate(rule=other_rule)
        with self.assertRaises(PermissionDenied):
            self.calculate(
                contract=other_contract,
                rule=other_rule,
                prior=first,
                operation="reverse",
                idempotency_key="other",
            )

    def test_failure_after_insert_rolls_back_calculation(self):
        original = IndexationCalculation.save

        def fail_after_save(record, *args, **kwargs):
            original(record, *args, **kwargs)
            raise RuntimeError("Synthetic post-insert failure")

        with (
            patch.object(IndexationCalculation, "save", fail_after_save),
            self.assertRaises(RuntimeError),
        ):
            self.calculate()
        self.assertEqual(IndexationCalculation.objects.count(), 0)
