"""Explicit financial gates and governed closeout transitions, no source writes."""

import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationMembership, OrganizationSettings
from apps.treasury.models import TreasuryMovement

from . import test_p10_s14_s17 as retained
from .financial_closeout import GATE_FAMILIES, financial_gate_snapshot
from .models import ProjectCloseoutEvent, ProjectCloseoutItemSnapshot
from .project_closeout import (
    cancel_closeout_case,
    coordinate_closeout_case,
    decide_closeout_case,
    requester_closeout_status,
    run_closeout_assessment,
)


class FinancialCloseoutTests(TestCase):
    setUpTestData = classmethod(
        retained.P10S14S17AcceptanceTests.setUpTestData.__func__
    )
    _grant = classmethod(retained.P10S14S17AcceptanceTests._grant.__func__)
    _case = retained.P10S14S17AcceptanceTests._case
    _assessment = retained.P10S14S17AcceptanceTests._assessment

    def setUp(self):
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"timezone": "Asia/Tehran"}
        )

    def snapshot(self, **kwargs):
        return financial_gate_snapshot(
            organization=self.organization,
            project=self.project,
            actor=self.runner,
            cutoff=timezone.now(),
            **kwargs,
        )

    def test_explicit_eight_families_absence_is_not_complete_and_no_source_writes(self):
        before = [x.objects.count() for x in (JournalEntry, TreasuryMovement)]
        snapshot = self.snapshot()
        self.assertEqual(set(snapshot["families"]), set(GATE_FAMILIES))
        self.assertEqual(snapshot["outcome"], "blocked")
        self.assertEqual(
            snapshot["families"]["project_cost_sources"]["outcome"], "unverifiable"
        )
        self.assertEqual(
            snapshot["families"]["treasury_gl"]["outcome"], "not_applicable"
        )
        self.assertEqual(
            snapshot["source_watermark"], self.snapshot()["source_watermark"]
        )
        self.assertEqual(
            before, [x.objects.count() for x in (JournalEntry, TreasuryMovement)]
        )
        case, assessment = self._assessment()
        item = assessment.items.get(family_code="reconciliation_performance")
        self.assertEqual(item.source_manifest["families"], snapshot["families"])
        self.assertEqual(item.outcome, "blocked")
        with self.assertRaises(ValidationError):
            decide_closeout_case(
                case=case,
                actor=self.reviewer,
                decision="accept",
                reason="No presence shortcut",
                operation_key="deny-presence",
                expected_revision=case.revision,
            )
        Path("docs/governance/cep/evidence/CEP-066_FINANCIAL_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "snapshot": snapshot,
                    "assessment": str(assessment.pk),
                    "native_financial_counts_before": before,
                    "native_financial_counts_after": [
                        x.objects.count() for x in (JournalEntry, TreasuryMovement)
                    ],
                    "acceptance_blocked": True,
                },
                indent=2,
                default=str,
            )
        )

    def test_settings_absent_is_explicit_unverified(self):
        OrganizationSettings.objects.filter(organization=self.organization).delete()
        data = self.snapshot()
        self.assertTrue(
            all(x["outcome"] == "unverifiable" for x in data["families"].values())
        )

    def test_denied_actor_and_foreign_project(self):
        with self.assertRaises(PermissionDenied):
            financial_gate_snapshot(
                organization=self.organization,
                project=self.other_project,
                actor=self.runner,
                cutoff=timezone.now(),
            )
        with self.assertRaises(PermissionDenied):
            financial_gate_snapshot(
                organization=self.organization,
                project=self.project,
                actor=self.outsider,
                cutoff=timezone.now(),
            )

    def test_protected_open_acceptance_and_exception_links_cannot_be_fabricated(self):
        case = self._case()
        for actor in (self.runner, self.reviewer):
            with self.assertRaises(PermissionDenied):
                coordinate_closeout_case(
                    case=case,
                    actor=actor,
                    reason="Synthetic open",
                    operation_key="untrusted-open",
                    details={"accepted_open_obligations": [str(uuid4())]},
                )
        with self.assertRaises(PermissionDenied):
            coordinate_closeout_case(
                case=case,
                actor=self.runner,
                reason="Foreign exception",
                operation_key="untrusted-exception",
                details={"blocking_exception_ids": [str(uuid4())]},
            )
        self.assertFalse(ProjectCloseoutEvent.objects.filter(case=case).exists())

    def test_requester_projection_does_not_return_reviewer_or_security_metadata(self):
        case = self._case()
        coordinate_closeout_case(
            case=case,
            actor=self.reviewer,
            reason="Confidential review",
            operation_key="private-review",
            details={"confidential": "test security metadata"},
        )
        self.assertEqual(
            set(
                requester_closeout_status(
                    organization=self.organization, actor=self.runner, case_id=case.pk
                )
            ),
            {"case", "status", "revision"},
        )
        with self.assertRaises(PermissionDenied):
            requester_closeout_status(
                organization=self.organization, actor=self.reviewer, case_id=case.pk
            )

    def test_rejection_retry_revoked_actor_and_successor_keep_history(self):
        case, original = self._assessment()
        event = decide_closeout_case(
            case=case,
            actor=self.reviewer,
            decision="reject",
            reason="Unresolved source evidence",
            operation_key="reject",
            expected_revision=case.revision,
        )
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(event.pk)).exists())
        other = self.reviewer
        OrganizationMembership.objects.filter(
            organization=self.organization, user=other
        ).update(status="suspended")
        with self.assertRaises(PermissionDenied):
            decide_closeout_case(
                case=case,
                actor=other,
                decision="reject",
                reason="Unresolved source evidence",
                operation_key="reject",
                expected_revision=case.revision,
            )
        case.refresh_from_db()
        successor = run_closeout_assessment(
            case=case,
            actor=self.runner,
            idempotency_key="corrected",
            expected_revision=case.revision,
        )
        self.assertEqual(successor.supersedes_id, original.pk)
        self.assertEqual(original.items.count(), 9)
        self.assertEqual(event.new_state, "rejected")

    def test_creator_cancel_is_atomic_append_only_and_never_mutates_finance(self):
        case = self._case()
        before = TreasuryMovement.objects.count()
        with self.assertRaises(PermissionDenied):
            cancel_closeout_case(
                case=case,
                actor=self.reviewer,
                reason="Wrong initiator",
                operation_key="cancel",
                expected_revision=case.revision,
            )
        event = cancel_closeout_case(
            case=case,
            actor=self.runner,
            reason="Withdraw pending case",
            operation_key="cancel",
            expected_revision=case.revision,
        )
        replay = cancel_closeout_case(
            case=case,
            actor=self.runner,
            reason="Withdraw pending case",
            operation_key="cancel",
            expected_revision=case.revision,
        )
        self.assertEqual(event.pk, replay.pk)
        self.assertEqual(TreasuryMovement.objects.count(), before)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(event.pk)).exists())
        with self.assertRaises(ValidationError):
            event.reason = "Silent edit"
            event.save()
        case.refresh_from_db()
        self.assertEqual(case.status, "cancelled")

    def test_financial_capture_exception_rolls_back_native_case_assessment_and_audit(
        self,
    ):
        case = self._case()
        before = (
            case.revision,
            ProjectCloseoutItemSnapshot.objects.count(),
            AuditEvent.objects.count(),
        )
        with (
            patch(
                "apps.reporting.project_closeout.financial_gate_snapshot",
                side_effect=ValidationError("source changed"),
            ),
            self.assertRaises(ValidationError),
        ):
            run_closeout_assessment(
                case=case, actor=self.runner, idempotency_key="failed"
            )
        case.refresh_from_db()
        self.assertEqual(
            before,
            (
                case.revision,
                ProjectCloseoutItemSnapshot.objects.count(),
                AuditEvent.objects.count(),
            ),
        )


class NativeTreasuryCloseoutTests(TestCase):
    def setUp(self):
        from apps.treasury.test_cep061 import PayrollTreasuryFixture

        # Reuse only native setup; no imported TestCase class collection.
        fixture = PayrollTreasuryFixture()
        fixture.setUp()
        self.fixture = fixture
        from apps.organizations.models import BusinessPermission

        fixture.organization.memberships.get(
            user=fixture.owner
        ).role_definition.permissions.add(*BusinessPermission.objects.all())

    def test_native_posted_cash_requires_current_exact_slice_and_keeps_revision(self):
        from apps.treasury.services import run_treasury_gl_reconciliation

        f = self.fixture
        from decimal import Decimal

        from apps.projects.models import Project
        from apps.treasury.services import create_movement

        project = Project.objects.create(
            organization=f.organization,
            code="CLOSE-CASH",
            name="Scoped cash",
            created_by=f.owner,
        )
        movement = create_movement(
            organization=f.organization,
            actor=f.owner,
            kind="receipt",
            movement_date=timezone.now().date(),
            amount=Decimal(100),
            description="Synthetic cash",
            idempotency_key="native-closeout-cash",
            account=f.cash.bank,
            project=project,
        )
        f.cash.post(movement)
        kwargs = {
            "organization": f.organization,
            "project": project,
            "actor": f.owner,
            "cutoff": timezone.now(),
        }
        initial = financial_gate_snapshot(**kwargs)
        self.assertEqual(initial["families"]["treasury_gl"]["outcome"], "blocked")
        first = run_treasury_gl_reconciliation(
            organization=f.organization,
            actor=f.owner,
            cutoff_date=kwargs["cutoff"].date(),
        )
        result = financial_gate_snapshot(**kwargs)
        self.assertEqual(result["families"]["treasury_gl"]["outcome"], "satisfied")
        second = run_treasury_gl_reconciliation(
            organization=f.organization,
            actor=f.owner,
            cutoff_date=kwargs["cutoff"].date(),
        )
        current = financial_gate_snapshot(**kwargs)
        rows = current["families"]["treasury_gl"]["evidence"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["native_slice"], str(second.slices.get().pk))
        self.assertNotEqual(first.pk, second.pk)
        Path("docs/governance/cep/evidence/CEP-066_TREASURY_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "native_movement": str(movement.pk),
                    "first_native_run": str(first.pk),
                    "second_native_run": str(second.pk),
                    "read_only_result": current,
                },
                indent=2,
                default=str,
            )
        )
        self.assertEqual(
            current["families"]["accounting_period_controls"]["outcome"], "blocked"
        )
