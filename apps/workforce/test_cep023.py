"""Executable leave authority evidence with explicit synthetic policy inputs."""

from datetime import date, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.organizations.services import create_organization_with_owner
from apps.timekeeping.models import LeaveMissionRequest, RequestState
from apps.timekeeping.services import (
    create_leave_mission_request,
    review_time_request,
    submit_time_request,
)

from . import leave_services as service
from .leave_models import LeaveBalanceEntry, LeavePolicyVersion
from .leave_models import LeaveEntryKind as K
from .models import Employee
from .person_services import create_person, create_work_relationship


class LeaveAuthorityTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(username="cep023-owner")
        self.organization = create_organization_with_owner(
            owner=self.actor, name="CEP023", slug="cep023"
        )
        self.codes = [
            P.LEAVE_POLICIES_MANAGE,
            P.LEAVE_BALANCES_MANAGE,
            P.LEAVE_BALANCES_VIEW,
            P.LEAVE_MISSION_REQUEST,
            P.LEAVE_MISSION_REVIEW,
        ]
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(code__in=self.codes)
        )
        self.reviewer = User.objects.create_user(username="cep023-reviewer")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="leave-reviewer",
            name="Reviewer",
            created_by=self.actor,
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=self.codes))
        reviewer_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.reviewer,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            assigned_by=self.actor,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=reviewer_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit synthetic reviewer scope",
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="L1",
            first_name="Synthetic",
            last_name="Worker",
        )
        person = create_person(
            organization=self.organization,
            actor=self.actor,
            first_name="Synthetic",
            last_name="Worker",
        )
        self.relationship = create_work_relationship(
            organization=self.organization,
            actor=self.actor,
            person=person,
            employee_number="L1",
            effective_start=date(2025, 1, 1),
            legacy_employee=self.employee,
        )
        self.other_actor = User.objects.create_user(username="cep023-other")
        self.other = create_organization_with_owner(
            owner=self.other_actor, name="Other", slug="cep023-other"
        )
        for assigned in membership.role_assignments.select_related("role"):
            assigned.role.permissions.add(
                *BusinessPermission.objects.filter(code__in=self.codes)
            )

    def policy(self, **changes):
        args = {
            "organization": self.organization,
            "actor": self.actor,
            "category_code": "EXPLICIT",
            "effective_from": date(2026, 1, 1),
            "effective_to": date(2027, 1, 1),
            "unit": "minutes",
            "accrual_preset": "ZERO_ACCRUAL",
            "entitlement_rule_reference": "approved-test-entitlement-rule",
            "accrual_rule_reference": "",
            "negative_balance_threshold": D(0),
            "carry_forward_limit": None,
            "expiry_rule_reference": "",
            "evidence_reference": "synthetic-policy-approval",
            "reason": "Explicit synthetic policy",
        }
        return service.record_policy(**(args | changes))

    def credit(self, **changes):
        args = {
            "organization": self.organization,
            "actor": self.actor,
            "relationship": self.relationship,
            "category_code": "EXPLICIT",
            "effective_on": date(2026, 1, 1),
            "kind": K.ENTITLEMENT,
            "quantity": D(1000),
            "rule_reference": "approved-test-entitlement-rule",
            "source_key": "test-entitlement-source",
            "evidence_reference": "synthetic-rule-outcome",
            "reason": "Explicit synthetic source quantity",
        }
        return service.record_credit(**(args | changes))

    def balance(self, **changes):
        return service.balance_as_of(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "relationship": self.relationship,
                    "category_code": "EXPLICIT",
                    "as_of": date(2026, 3, 1),
                }
                | changes
            )
        )

    def request(self, **changes):
        zone = ZoneInfo("Asia/Tehran")
        return create_leave_mission_request(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "employee": self.employee,
                    "kind": "leave",
                    "category_code": "EXPLICIT",
                    "starts_at": datetime(2026, 2, 1, 8, tzinfo=zone),
                    "ends_at": datetime(2026, 2, 1, 12, tzinfo=zone),
                    "reason": "Synthetic request",
                    "policy_reference": "synthetic-policy-approval",
                }
                | changes
            )
        )

    def reserve(self, request, **changes):
        return service.reserve_request(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "relationship": self.relationship,
                    "request": request,
                    "quantity": D(240),
                    "effective_on": date(2026, 1, 31),
                    "source_key": "reservation-source",
                    "evidence_reference": "explicit-quantity-evidence",
                    "reason": "Approved quantity in policy unit",
                }
                | changes
            )
        )

    def approved(self):
        self.policy()
        self.credit()
        request = self.request()
        self.reserve(request)
        submit_time_request(
            organization=self.organization, actor=self.actor, request=request
        )
        review_time_request(
            organization=self.organization,
            actor=self.reviewer,
            request=request,
            approve=True,
            reason="Independent native approval",
        )
        return request

    def test_policy_and_initial_balance_absence_fail_closed(self):
        with self.assertRaises(ValidationError):
            self.balance()
        with self.assertRaises(ValidationError):
            self.credit()
        self.policy()
        with self.assertRaises(ValidationError):
            self.balance()
        with self.assertRaises(ValidationError):
            self.reserve(self.request())
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_authoritative_asof_projection_source_ids_and_recorded_cutoff(self):
        policy = self.policy()
        first = self.credit()
        self.credit(
            kind=K.ADJUSTMENT,
            effective_on=date(2026, 4, 1),
            quantity=D(-100),
            source_key="future-correction",
        )
        result = self.balance(recorded_before=first.created_at)
        self.assertEqual(
            (
                result.quantity,
                result.available,
                result.unit,
                result.policy_id,
                result.source_ids,
            ),
            (D(1000), D(1000), "minutes", policy.pk, (first.pk,)),
        )
        self.assertEqual(self.balance(as_of=date(2026, 4, 1)).quantity, D(900))

    def test_policy_versions_preserve_prior_identity_and_knowledge_cutoff(self):
        first = self.policy()
        self.credit()
        second = self.policy(
            supersedes=first,
            reason="Correct explicit threshold",
            negative_balance_threshold=D(-10),
        )
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertEqual(self.balance().policy_id, second.pk)
        self.assertEqual(
            service._policy(
                self.organization, "EXPLICIT", date(2026, 3, 1), first.created_at
            ).pk,
            first.pk,
        )
        first.refresh_from_db()
        self.assertEqual(first.negative_balance_threshold, D(0))
        with self.assertRaises(ValidationError):
            self.policy(supersedes=first)
        with self.assertRaises(ValidationError):
            self.policy()

    def test_record_and_queryset_history_are_immutable(self):
        policy = self.policy()
        entry = self.credit()
        for record in (policy, entry):
            with self.assertRaises(ValidationError):
                record.save()
            with self.assertRaises(ValidationError):
                record.delete()
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).update(reason="overwrite")
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).delete()

    def test_credit_retry_is_idempotent_and_mismatch_rejected(self):
        self.policy()
        first = self.credit()
        self.assertEqual(self.credit().pk, first.pk)
        with self.assertRaises(ValidationError):
            self.credit(quantity=D(1001))
        self.assertEqual(LeaveBalanceEntry.objects.count(), 1)

    def test_explicit_correction_reverses_and_preserves_source(self):
        self.policy()
        source = self.credit()
        args = {
            "organization": self.organization,
            "actor": self.actor,
            "source": source,
            "effective_on": date(2026, 2, 1),
            "source_key": "correct-source",
            "evidence_reference": "approved-correction",
            "reason": "Retain original",
        }
        correction = service.reverse_credit(**args)
        self.assertEqual(service.reverse_credit(**args).pk, correction.pk)
        self.assertEqual(correction.reverses_id, source.pk)
        self.assertEqual(self.balance().quantity, D(0))
        source.refresh_from_db()
        self.assertEqual(source.quantity, D(1000))

    def test_no_accrual_default_carry_limit_expiry_or_opening_import(self):
        self.policy()
        for changes in [
            {"kind": K.ACCRUAL},
            {"kind": K.CARRY_FORWARD},
            {"kind": K.EXPIRY, "quantity": D(-1)},
            {"kind": K.OPENING},
            {"quantity": 1000.0},
            {"quantity": D("NaN")},
            {"quantity": D("0.00001")},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.credit(**changes)
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_explicit_policy_defined_rule_outcomes_and_limits(self):
        self.policy(
            accrual_preset="POLICY_DEFINED",
            accrual_rule_reference="approved-test-accrual",
            carry_forward_limit=D(20),
            expiry_rule_reference="approved-test-expiry",
        )
        self.credit()
        self.credit(
            kind=K.ACCRUAL,
            quantity=D(10),
            rule_reference="approved-test-accrual",
            source_key="accrual-evidence",
        )
        self.credit(kind=K.CARRY_FORWARD, quantity=D(20), source_key="carry-evidence")
        self.credit(
            kind=K.EXPIRY,
            quantity=D(-5),
            rule_reference="approved-test-expiry",
            source_key="expiry-evidence",
        )
        self.assertEqual(self.balance().quantity, D(1025))
        with self.assertRaises(ValidationError):
            self.credit(kind=K.CARRY_FORWARD, quantity=D(21), source_key="excess-carry")

    def test_native_submission_and_approval_cannot_bypass_reservation(self):
        request = self.request()
        with self.assertRaises(ValidationError):
            submit_time_request(
                organization=self.organization, actor=self.actor, request=request
            )
        LeaveMissionRequest.objects.filter(pk=request.pk).update(
            state=RequestState.SUBMITTED
        )
        with self.assertRaises(ValidationError):
            review_time_request(
                organization=self.organization,
                actor=self.reviewer,
                request=request,
                approve=True,
                reason="Text alone is insufficient",
            )
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_reservation_consumption_cancellation_and_retry_are_atomic(self):
        request = self.approved()
        balance = self.balance()
        self.assertEqual(
            (balance.quantity, balance.reserved, balance.available),
            (D(1000), D(240), D(760)),
        )
        args = {
            "organization": self.organization,
            "actor": self.reviewer,
            "request": request,
            "occurred_on": date(2026, 2, 1),
            "evidence_reference": "approved-occurrence",
            "reason": "Evidenced completed occurrence",
        }
        consumption = service.consume_approved_occurrence(**args)
        self.assertEqual(service.consume_approved_occurrence(**args).pk, consumption.pk)
        self.assertEqual(
            (self.balance().quantity, self.balance().reserved), (D(760), D(0))
        )
        cancel = {
            "organization": self.organization,
            "actor": self.reviewer,
            "request": request,
            "effective_on": date(2026, 2, 2),
            "evidence_reference": "approved-cancellation",
            "reason": "Governed cancellation",
        }
        reinstatement = service.cancel_request(**cancel)
        self.assertEqual(service.cancel_request(**cancel).pk, reinstatement.pk)
        self.assertEqual(reinstatement.reverses_id, consumption.pk)
        self.assertEqual(
            (self.balance().quantity, self.balance().reserved), (D(1000), D(0))
        )
        request.refresh_from_db()
        self.assertEqual(request.state, RequestState.CANCELLED)
        with self.assertRaises(ValidationError):
            service.consume_approved_occurrence(**args)

    def test_rejected_request_releases_without_consuming(self):
        self.policy()
        self.credit()
        request = self.request()
        self.reserve(request)
        submit_time_request(
            organization=self.organization, actor=self.actor, request=request
        )
        review_time_request(
            organization=self.organization,
            actor=self.reviewer,
            request=request,
            approve=False,
            reason="Rejected by assigned authority",
        )
        self.assertEqual(
            (self.balance().quantity, self.balance().reserved), (D(1000), D(0))
        )
        self.assertFalse(LeaveBalanceEntry.objects.filter(kind=K.CONSUMPTION).exists())

    def test_cancel_unconsumed_approved_request_releases_only(self):
        request = self.approved()
        service.cancel_request(
            organization=self.organization,
            actor=self.reviewer,
            request=request,
            effective_on=date(2026, 2, 1),
            evidence_reference="approved-cancel",
            reason="Cancel before consumption",
        )
        self.assertEqual(
            (self.balance().quantity, self.balance().reserved), (D(1000), D(0))
        )
        self.assertFalse(
            LeaveBalanceEntry.objects.filter(kind=K.REINSTATEMENT).exists()
        )

    def test_overspend_and_backdated_correction_rollback_all_source_writes(self):
        self.policy()
        source = self.credit()
        request = self.request()
        with self.assertRaises(ValidationError):
            self.reserve(request, quantity=D(1001))
        self.reserve(request)
        before = LeaveBalanceEntry.objects.count()
        with self.assertRaises(ValidationError):
            service.reverse_credit(
                organization=self.organization,
                actor=self.actor,
                source=source,
                effective_on=date(2026, 1, 2),
                source_key="unsafe-reversal",
                evidence_reference="correction",
                reason="Would invalidate later reservation",
            )
        self.assertEqual(LeaveBalanceEntry.objects.count(), before)

    def test_consumption_requires_approved_completed_occurrence_and_evidence(self):
        self.policy()
        self.credit()
        request = self.request()
        self.reserve(request)
        with self.assertRaises(ValidationError):
            service.consume_approved_occurrence(
                organization=self.organization,
                actor=self.reviewer,
                request=request,
                occurred_on=date(2026, 2, 1),
                evidence_reference="event",
                reason="Not approved",
            )
        submit_time_request(
            organization=self.organization, actor=self.actor, request=request
        )
        review_time_request(
            organization=self.organization,
            actor=self.reviewer,
            request=request,
            approve=True,
            reason="Approve",
        )
        before = LeaveBalanceEntry.objects.count()
        with self.assertRaises(ValidationError):
            service.consume_approved_occurrence(
                organization=self.organization,
                actor=self.reviewer,
                request=request,
                occurred_on=date(2026, 2, 1),
                evidence_reference="",
                reason="No evidence",
            )
        self.assertEqual(LeaveBalanceEntry.objects.count(), before)
        with self.assertRaises(PermissionDenied):
            service.cancel_request(
                organization=self.organization,
                actor=self.actor,
                request=request,
                effective_on=date(2026, 2, 2),
                evidence_reference="self",
                reason="Self cancel",
            )

    def test_tenant_permission_membership_and_suspension_fail_closed(self):
        self.policy()
        self.credit()
        for kwargs in [
            {"actor": self.other_actor},
            {"organization": self.other, "actor": self.other_actor},
        ]:
            with self.assertRaises(PermissionDenied):
                self.balance(**kwargs)
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        OrganizationRole.permissions.through.objects.filter(
            organizationrole__in=[
                membership.role_definition_id,
                *membership.role_assignments.values_list("role_id", flat=True),
            ],
            businesspermission__code=P.LEAVE_BALANCES_VIEW,
        ).delete()
        with self.assertRaises(PermissionDenied):
            self.balance()
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=P.LEAVE_BALANCES_VIEW)
        )
        Organization.objects.filter(pk=self.organization.pk).update(status="suspended")
        with self.assertRaises(PermissionDenied):
            self.credit(source_key="suspended-write")

    def test_request_identity_is_explicit_and_foreign_policy_replacement_denied(self):
        policy = self.policy()
        self.credit()
        foreign_employee = Employee.objects.create(
            organization=self.other,
            employee_number="OTHER",
            first_name="Other",
            last_name="Worker",
        )
        request = self.request()
        self.relationship.legacy_employee = None
        from .models import WorkRelationship

        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            legacy_employee=None
        )
        with self.assertRaises(ValidationError):
            self.reserve(request)
        with self.assertRaises(PermissionDenied):
            self.policy(
                organization=self.other, actor=self.other_actor, supersedes=policy
            )
        self.assertIsNotNone(foreign_employee.pk)

    def test_no_future_occurrence_or_unconfigured_policy_interval(self):
        self.policy()
        self.credit()
        with self.assertRaises(ValidationError):
            self.balance(as_of=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            self.policy(
                accrual_preset="POLICY_DEFINED",
                supersedes=LeavePolicyVersion.objects.get(),
            )

    def test_foreign_request_and_invalid_reservation_sources_fail_closed(self):
        self.policy()
        self.credit()
        request = self.request()
        with self.assertRaises(PermissionDenied):
            service.reserve_request(
                organization=self.other,
                actor=self.other_actor,
                relationship=self.relationship,
                request=request,
                quantity=D(1),
                effective_on=date(2026, 1, 31),
                source_key="foreign",
                evidence_reference="x",
                reason="x",
            )
        for changes in [
            {"quantity": D(-1)},
            {"effective_on": date(2026, 2, 2)},
            {"evidence_reference": ""},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.reserve(request, **changes)
        self.assertEqual(LeaveBalanceEntry.objects.count(), 1)

    def test_policy_correction_cannot_invalidate_recorded_balances(self):
        policy = self.policy(negative_balance_threshold=D(-10))
        self.credit(quantity=D(5))
        self.credit(kind=K.ADJUSTMENT, quantity=D(-10), source_key="approved-negative")
        with self.assertRaises(ValidationError):
            self.policy(supersedes=policy, negative_balance_threshold=D(0))
        self.assertEqual(LeavePolicyVersion.objects.count(), 1)
        self.assertEqual(self.balance().available, D(-5))

    def test_request_fact_changes_cannot_reuse_a_stale_reservation(self):
        self.policy()
        self.credit()
        request = self.request()
        self.reserve(request)
        request.ends_at += timedelta(hours=1)
        request.save()
        with self.assertRaises(ValidationError):
            submit_time_request(
                organization=self.organization, actor=self.actor, request=request
            )
        request.refresh_from_db()
        self.assertEqual(request.state, RequestState.DRAFT)

    def test_future_occurrence_and_terminated_episode_are_rejected(self):
        request = self.approved()
        original_end = request.ends_at
        LeaveMissionRequest.objects.filter(pk=request.pk).update(
            ends_at=timezone.now() + timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            service.consume_approved_occurrence(
                organization=self.organization,
                actor=self.reviewer,
                request=request,
                occurred_on=date(2026, 2, 1),
                evidence_reference="future",
                reason="Cannot consume future leave",
            )
        LeaveMissionRequest.objects.filter(pk=request.pk).update(ends_at=original_end)
        with self.assertRaises(ValidationError):
            service.consume_approved_occurrence(
                organization=self.organization,
                actor=self.reviewer,
                request=request,
                occurred_on=date(2026, 2, 2),
                evidence_reference="wrong-date",
                reason="Date mismatches approved occurrence",
            )
