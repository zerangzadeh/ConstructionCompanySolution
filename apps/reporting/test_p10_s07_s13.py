from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.permission_registry import PERMISSION_RESOURCES
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.projects.models import Project
from apps.reporting.models import (
    ReconciliationException,
    ReconciliationOutcome,
    ReconciliationPairDefinition,
    ReconciliationPairVersion,
    ReconciliationRebuildCheck,
    ReconciliationRun,
    ReconciliationRunReview,
    ReconciliationSideSnapshot,
)
from apps.reporting.reconciliation import (
    ADAPTERS,
    PairData,
    SideData,
    _compare,
    execute_reconciliation,
    reconciliation_drillthrough,
    record_exception_event,
    replay_reconciliation,
    review_reconciliation_run,
)
from apps.reporting.reconciliation_catalog import (
    RECONCILIATION_PAIR_SPECS as CURRENT_PAIR_SPECS,
)

# This historical acceptance suite owns the original thirteen financial pairs.
# CEP050's context-required workforce pair has its own native-source suite.
RECONCILIATION_PAIR_SPECS = {
    code: spec
    for code, spec in CURRENT_PAIR_SPECS.items()
    if code != "attendance_timesheet"
}

RECONCILIATION_PERMISSIONS = {
    value
    for value in BusinessPermissionCode.values
    if value.startswith("reporting.reconciliation")
}


class P10S07S13AcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_user(username="p10-recon-runner", password="x")
        cls.reviewer = User.objects.create_user(
            username="p10-recon-reviewer", password="x"
        )
        cls.other = User.objects.create_user(username="p10-recon-other", password="x")
        cls.organization = Organization.objects.create(
            name="P10 Reconciliation Tenant",
            slug="p10-reconciliation",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.other_organization = Organization.objects.create(
            name="Other Reconciliation Tenant",
            slug="other-reconciliation",
            created_by=cls.other,
            updated_by=cls.other,
        )
        cls.project = Project.objects.create(
            organization=cls.organization,
            code="P10-REC",
            name="پروژه تطبیق",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls._grant(cls.user, set(BusinessPermissionCode.values))
        cls._grant(cls.reviewer, set(BusinessPermissionCode.values))

    @classmethod
    def _grant(cls, user: User, permissions: set[str]) -> OrganizationMembership:
        membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=user,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        role = OrganizationRole.objects.create(
            organization=cls.organization,
            code=f"recon-{user.username}",
            name=f"Recon {user.username}",
            created_by=cls.user,
            updated_by=cls.user,
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=permissions))
        MembershipRoleAssignment.objects.create(
            organization=cls.organization,
            membership=membership,
            role=role,
            reason="P10 S07-S13 focused acceptance",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P10 S07-S13 focused acceptance",
        )
        return membership

    def _run(
        self, code: str = "estimate_budget", key: str = "recon-run"
    ) -> ReconciliationRun:
        return execute_reconciliation(
            organization=self.organization,
            actor=self.user,
            pair_code=code,
            idempotency_key=key,
            cutoff_at=timezone.now().replace(microsecond=0),
        )

    def test_01_catalogue_contains_exactly_thirteen_governed_pairs(self) -> None:
        self.assertEqual(
            set(RECONCILIATION_PAIR_SPECS),
            set(
                ReconciliationPairDefinition.objects.exclude(
                    code="attendance_timesheet"
                ).values_list("code", flat=True)
            ),
        )
        self.assertEqual(
            ReconciliationPairVersion.objects.filter(status="published")
            .exclude(definition__code="attendance_timesheet")
            .count(),
            13,
        )

    def test_02_permissions_registered_and_owner_admin_defaults_denied(self) -> None:
        self.assertEqual(len(RECONCILIATION_PERMISSIONS), 15)
        registered = {
            str(code)
            for resource in PERMISSION_RESOURCES
            if resource.key == "reporting"
            for code in resource.permissions
        }
        self.assertTrue(RECONCILIATION_PERMISSIONS.issubset(registered))
        for permissions in (
            DEFAULT_ROLE_PERMISSIONS[role] for role in ("tenant_owner", "tenant_admin")
        ):
            self.assertTrue(RECONCILIATION_PERMISSIONS.isdisjoint(permissions))

    def test_03_all_thirteen_pairs_execute_without_fabricating_zero(self) -> None:
        for code in RECONCILIATION_PAIR_SPECS:
            run = self._run(code=code, key=f"all-pairs-{code}")
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.side_snapshots.count(), 2)
            self.assertIn(run.tie_out.outcome, ReconciliationOutcome.values)
            for side in run.side_snapshots.all():
                if side.readiness != "ready":
                    self.assertIsNone(side.value.get("amount"))

    def test_04_tenant_isolation_rejects_foreign_run_drillthrough(self) -> None:
        run = self._run(key="tenant-isolation")
        with self.assertRaises(PermissionDenied):
            reconciliation_drillthrough(
                organization=self.other_organization,
                actor=self.other,
                run_id=str(run.pk),
            )

    def test_05_source_permissions_are_rechecked(self) -> None:
        limited = User.objects.create_user(username="limited-recon", password="x")
        self._grant(
            limited,
            {BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_EXECUTE},
        )
        with self.assertRaises(PermissionDenied):
            execute_reconciliation(
                organization=self.organization,
                actor=limited,
                pair_code="estimate_budget",
                idempotency_key="source-denied",
            )

    def test_06_idempotent_retry_returns_one_run(self) -> None:
        cutoff = timezone.now().replace(microsecond=0)
        first = execute_reconciliation(
            organization=self.organization,
            actor=self.user,
            pair_code="estimate_budget",
            idempotency_key="same-run",
            cutoff_at=cutoff,
        )
        second = execute_reconciliation(
            organization=self.organization,
            actor=self.user,
            pair_code="estimate_budget",
            idempotency_key="same-run",
            cutoff_at=cutoff,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            ReconciliationRun.objects.filter(idempotency_key="same-run").count(), 1
        )

    def test_07_idempotency_collision_fails_closed(self) -> None:
        self._run(key="collision")
        with self.assertRaises(ValidationError):
            execute_reconciliation(
                organization=self.organization,
                actor=self.user,
                pair_code="treasury_gl",
                idempotency_key="collision",
            )

    def test_08_unknown_is_not_zero_or_a_match(self) -> None:
        run = self._run(key="unknown-not-zero")
        self.assertEqual(run.tie_out.outcome, ReconciliationOutcome.UNKNOWN)
        self.assertEqual(run.tie_out.difference, {})
        self.assertTrue(
            all(side.value["amount"] is None for side in run.side_snapshots.all())
        )

    def test_09_gated_consumer_is_explicit(self) -> None:
        run = self._run(code="contractor_compliance", key="gated")
        self.assertEqual(run.tie_out.outcome, ReconciliationOutcome.GATED)
        self.assertEqual(run.tie_out.coverage["right"], "gated_not_activated")

    def test_10_unapproved_tolerance_does_not_hide_a_difference(self) -> None:
        data = PairData(
            SideData("L", "left.Model", "ready", {"amount": "10.00"}, {"ids": ["1"]}),
            SideData("R", "right.Model", "ready", {"amount": "9.99"}, {"ids": ["2"]}),
            "amount",
        )
        outcome, difference, tolerance, materiality = _compare(
            data,
            {"tolerance": {"absolute": "0.01"}, "materiality": {"absolute": "1.00"}},
        )
        self.assertEqual(outcome, ReconciliationOutcome.MISMATCH)
        self.assertEqual(Decimal(difference["amount"]), Decimal("0.01"))
        self.assertTrue(tolerance["difference_visible"])
        self.assertFalse(tolerance["applied"])
        self.assertTrue(materiality["material"])

    def test_11_side_and_tieout_snapshots_are_immutable(self) -> None:
        run = self._run(key="immutable")
        side = run.side_snapshots.first()
        side.readiness = "ready"
        with self.assertRaises(ValidationError):
            side.save()
        run.tie_out.difference = {"amount": "0"}
        with self.assertRaises(ValidationError):
            run.tie_out.save()

    def test_12_material_runner_cannot_review_own_run(self) -> None:
        run = self._run(key="review-sod")
        with self.assertRaises(PermissionDenied):
            review_reconciliation_run(
                run=run, reviewer=self.user, decision="accepted", reason="self"
            )

    def test_13_independent_run_review_is_immutable(self) -> None:
        run = self._run(key="independent-review")
        review = review_reconciliation_run(
            run=run, reviewer=self.reviewer, decision="accepted", reason="مستقل"
        )
        self.assertIsInstance(review, ReconciliationRunReview)
        review.reason = "changed"
        with self.assertRaises(ValidationError):
            review.save()

    def test_14_exception_snapshot_has_exact_side_lineage(self) -> None:
        run = self._run(key="exception-lineage")
        exception = run.exceptions.get()
        left_snapshot = run.side_snapshots.get(side="left")
        self.assertEqual(exception.left_lineage["model"], left_snapshot.authority_model)
        self.assertEqual(
            exception.left_lineage["ids"], left_snapshot.source_manifest["ids"]
        )
        self.assertTrue(exception.snapshot_hash)
        self.assertEqual(
            exception.evidence_manifest["pair_version"], str(run.pair_version_id)
        )

    def test_15_exception_event_is_idempotent_and_append_only(self) -> None:
        exception = self._run(key="event").exceptions.get()
        first = record_exception_event(
            exception=exception,
            actor=self.user,
            action="disposition",
            reason="منبع باید اصلاح شود",
            operation_key="disposition-key",
            correction_reference={"source": "SRC-1"},
        )
        second = record_exception_event(
            exception=exception,
            actor=self.user,
            action="disposition",
            reason="منبع باید اصلاح شود",
            operation_key="disposition-key",
            correction_reference={"source": "SRC-1"},
        )
        self.assertEqual(first.pk, second.pk)
        first.reason = "changed"
        with self.assertRaises(ValidationError):
            first.save()

    def test_16_last_disposer_cannot_close_material_exception(self) -> None:
        exception = self._run(key="close-sod").exceptions.get()
        record_exception_event(
            exception=exception,
            actor=self.user,
            action="disposition",
            reason="تصمیم",
            operation_key="dispose-close",
        )
        with self.assertRaises(PermissionDenied):
            record_exception_event(
                exception=exception,
                actor=self.user,
                action="close",
                reason="بستن",
                operation_key="close-self",
            )

    def test_17_independent_close_and_controlled_reopen_preserve_history(self) -> None:
        exception = self._run(key="reopen").exceptions.get()
        record_exception_event(
            exception=exception,
            actor=self.user,
            action="disposition",
            reason="تصمیم",
            operation_key="reopen-dispose",
        )
        record_exception_event(
            exception=exception,
            actor=self.reviewer,
            action="close",
            reason="بررسی مستقل",
            operation_key="reopen-close",
        )
        record_exception_event(
            exception=exception,
            actor=self.user,
            action="reopen",
            reason="شاهد جدید",
            operation_key="reopen-event",
        )
        self.assertEqual(
            list(exception.events.values_list("new_state", flat=True)),
            ["disposition_recorded", "closed", "reopened"],
        )

    def test_18_exact_replay_does_not_rewrite_historical_run(self) -> None:
        run = self._run(key="replay")
        original_hash = run.tie_out.calculation_hash
        check = replay_reconciliation(
            original_run=run, actor=self.user, idempotency_key="replay-check"
        )
        run.refresh_from_db()
        self.assertEqual(check.outcome, ReconciliationRebuildCheck.Outcome.MATCHED)
        self.assertEqual(run.tie_out.calculation_hash, original_hash)
        self.assertIsNone(run.replaces_id)

    def test_19_successor_recalculation_links_without_overwrite(self) -> None:
        original = self._run(key="successor-original")
        successor = execute_reconciliation(
            organization=self.organization,
            actor=self.user,
            pair_code="estimate_budget",
            idempotency_key="successor-new",
            replaces=original,
        )
        self.assertEqual(successor.replaces_id, original.pk)
        self.assertNotEqual(successor.pk, original.pk)
        self.assertTrue(ReconciliationRun.objects.filter(pk=original.pk).exists())
        original.refresh_from_db()
        self.assertEqual(original.replacement.pk, successor.pk)

    def test_20_drillthrough_rechecks_reporting_and_source_permissions(self) -> None:
        run = self._run(key="drillthrough")
        visible = reconciliation_drillthrough(
            organization=self.organization, actor=self.user, run_id=str(run.pk)
        )
        self.assertEqual(visible.pk, run.pk)
        self.assertEqual(visible.side_snapshots.count(), 2)

    def test_21_platform_or_unrelated_user_has_no_implicit_tenant_access(self) -> None:
        run = self._run(key="platform-separation")
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save(update_fields=["is_staff", "is_superuser"])
        with self.assertRaises(PermissionDenied):
            reconciliation_drillthrough(
                organization=self.organization, actor=self.other, run_id=str(run.pk)
            )

    def test_22_workbench_is_rtl_jalali_and_private(self) -> None:
        self._run(key="ui")
        self.client.force_login(self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("reporting:reconciliation_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "موضوع‌های تطبیق")
        self.assertContains(response, "نامعلوم")
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")

    def test_23_run_is_audited_without_source_mutation(self) -> None:
        project_count = Project.objects.count()
        run = self._run(key="audit-no-effect")
        self.assertEqual(Project.objects.count(), project_count)
        self.assertTrue(
            AuditEvent.objects.filter(
                entity_id=str(run.pk), action="reporting.reconciliation_run"
            ).exists()
        )

    def test_24_catalogue_and_urls_are_complete(self) -> None:
        self.assertEqual(
            set(RECONCILIATION_PAIR_SPECS), set(RECONCILIATION_PAIR_SPECS.keys())
        )
        self.assertIn(
            "/reporting/reconciliations/", reverse("reporting:reconciliation_workbench")
        )
        self.assertTrue(
            all(
                spec["source_permissions"]
                for spec in RECONCILIATION_PAIR_SPECS.values()
            )
        )
        self.assertEqual(ReconciliationSideSnapshot.objects.count(), 0)
        self.assertEqual(ReconciliationException.objects.count(), 0)

    def test_25_each_pair_retains_injected_mismatch_and_lineage(self) -> None:
        originals = ADAPTERS.copy()
        try:
            for index, code in enumerate(RECONCILIATION_PAIR_SPECS, start=1):
                ADAPTERS[code] = lambda organization, project, cutoff: PairData(
                    SideData(
                        "Left Authority",
                        "left.Model",
                        "ready",
                        {"amount": "10"},
                        {"model": "left.Model", "ids": ["left-1"]},
                    ),
                    SideData(
                        "Right Authority",
                        "right.Model",
                        "ready",
                        {"amount": "8"},
                        {"model": "right.Model", "ids": ["right-1"]},
                    ),
                    "amount",
                    currency="IRR",
                    unit="money",
                )
                run = self._run(code=code, key=f"injected-{index}-{code}")
                self.assertEqual(run.tie_out.outcome, ReconciliationOutcome.MISMATCH)
                exception = run.exceptions.get()
                self.assertEqual(exception.left_lineage["ids"], ["left-1"])
                self.assertEqual(exception.right_lineage["ids"], ["right-1"])
        finally:
            ADAPTERS.clear()
            ADAPTERS.update(originals)
