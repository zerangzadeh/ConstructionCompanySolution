from __future__ import annotations

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
    OrganizationStatus,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.permission_registry import PERMISSION_RESOURCES
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.projects.models import Project
from apps.reporting.catalog import METRIC_SPECS
from apps.reporting.models import (
    MetricDefinition,
    MetricDefinitionVersion,
    MetricExportManifest,
    MetricFreshness,
    MetricRefreshRun,
    MetricResult,
    MetricResultReview,
    MetricRunStatus,
)
from apps.reporting.services import (
    dashboard_results,
    drillthrough_manifest,
    export_dashboard_csv,
    refresh_metric,
    review_metric_result,
)

REPORTING_PERMISSIONS = {
    value for value in BusinessPermissionCode.values if value.startswith("reporting.")
}
METRIC_REPORTING_PERMISSIONS = {
    value
    for value in REPORTING_PERMISSIONS
    if not value.startswith("reporting.reconciliation")
    and not value.startswith("reporting.project_closeout")
}


class P10S02S06AcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_user(username="p10-owner", password="x")
        cls.reviewer = User.objects.create_user(username="p10-reviewer", password="x")
        cls.other_user = User.objects.create_user(username="p10-other", password="x")
        cls.organization = Organization.objects.create(
            name="P10 Tenant",
            slug="p10-tenant",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.other_organization = Organization.objects.create(
            name="Other P10 Tenant",
            slug="other-p10-tenant",
            created_by=cls.other_user,
            updated_by=cls.other_user,
        )
        cls.project_a = Project.objects.create(
            organization=cls.organization,
            code="P10-A",
            name="پروژه الف",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.project_b = Project.objects.create(
            organization=cls.organization,
            code="P10-B",
            name="پروژه ب",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.member = cls._grant(cls.user, organization_scope=True)
        cls.review_member = cls._grant(cls.reviewer, organization_scope=True)

    @classmethod
    def _grant(
        cls,
        user: User,
        *,
        organization_scope: bool = False,
        project: Project | None = None,
        permissions: set[str] | None = None,
    ) -> OrganizationMembership:
        membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=user,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        role = OrganizationRole.objects.create(
            organization=cls.organization,
            code=f"p10-{user.username}",
            name=f"P10 {user.username}",
            created_by=cls.user,
            updated_by=cls.user,
        )
        codes = permissions or (
            REPORTING_PERMISSIONS
            | {
                BusinessPermissionCode.PURCHASE_ORDERS_VIEW,
                BusinessPermissionCode.BUDGETS_VIEW,
                BusinessPermissionCode.PROJECT_COSTS_VIEW,
                BusinessPermissionCode.TREASURY_VIEW,
                BusinessPermissionCode.INVENTORY_VALUATION_VIEW,
            }
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
        MembershipRoleAssignment.objects.create(
            organization=cls.organization,
            membership=membership,
            role=role,
            reason="P10 focused acceptance",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.organization,
            membership=membership,
            scope_type=(
                AuthorizationScopeType.ORGANIZATION
                if organization_scope
                else AuthorizationScopeType.PROJECT
            ),
            project=project,
            reason="P10 focused acceptance scope",
        )
        return membership

    def _refresh(
        self, *, actor: User | None = None, key: str = "p10-refresh"
    ) -> MetricResult:
        return refresh_metric(
            organization=self.organization,
            actor=actor or self.user,
            metric_code="procurement_cycle_time",
            idempotency_key=key,
        )

    def _material_result(self, *, actor: User | None = None) -> MetricResult:
        version = MetricDefinitionVersion.objects.get(
            definition__code="approved_budget", status="published"
        )
        run = MetricRefreshRun.objects.create(
            organization=self.organization,
            metric_version=version,
            status=MetricRunStatus.SUCCEEDED,
            idempotency_key=f"material-{MetricRefreshRun.objects.count()}",
            request_fingerprint="a" * 64,
            requested_by=actor or self.user,
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        return MetricResult.objects.create(
            organization=self.organization,
            run=run,
            metric_code="approved_budget",
            value={"amount": "0"},
            currency="IRR",
            unit="money",
            as_of=timezone.now(),
            freshness=MetricFreshness.FRESH,
            coverage={"complete": True},
            source_manifest={"model": "projects.BudgetAllocation", "ids": []},
            calculation_hash="b" * 64,
        )

    def test_01_catalogue_contains_exactly_six_approved_metrics(self) -> None:
        self.assertEqual(
            set(MetricDefinition.objects.values_list("code", flat=True)),
            set(METRIC_SPECS),
        )
        self.assertEqual(
            MetricDefinitionVersion.objects.filter(status="published").count(), 6
        )

    def test_02_all_six_definitions_have_required_governance_fields(self) -> None:
        for definition in MetricDefinition.objects.all():
            self.assertTrue(definition.persian_name)
            self.assertTrue(definition.source_domain)
            self.assertTrue(definition.metric_owner)
            self.assertTrue(definition.source_owner)
            self.assertTrue(definition.source_permission)
            self.assertTrue(definition.drillthrough_route_name)
            result = refresh_metric(
                organization=self.organization,
                actor=self.user,
                metric_code=definition.code,
                idempotency_key=f"six-metrics-{definition.code}",
            )
            self.assertEqual(result.metric_code, definition.code)
            self.assertIn("scope_kind", result.source_manifest)
            self.assertEqual(result.freshness, MetricFreshness.INCOMPLETE)
            self.assertFalse(result.coverage["complete"])
            metric_values = [
                value
                for key, value in result.value.items()
                if key not in {"completed_cycles"}
            ]
            self.assertTrue(all(value is None for value in metric_values))

    def test_03_sixteen_permissions_are_default_denied(self) -> None:
        self.assertEqual(len(METRIC_REPORTING_PERMISSIONS), 16)
        registered = {
            str(code)
            for resource in PERMISSION_RESOURCES
            if resource.key == "reporting"
            for code in resource.permissions
        }
        self.assertEqual(registered, REPORTING_PERMISSIONS)
        for defaults in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertFalse(METRIC_REPORTING_PERMISSIONS & defaults)
        self.assertFalse(
            OrganizationRole.objects.filter(
                organization__isnull=True,
                permissions__code__in=METRIC_REPORTING_PERMISSIONS,
            ).exists()
        )

    def test_04_missing_permission_denies_runtime(self) -> None:
        denied = User.objects.create_user(username="p10-denied", password="x")
        self._grant(
            denied,
            organization_scope=True,
            permissions={BusinessPermissionCode.PURCHASE_ORDERS_VIEW},
        )
        with self.assertRaises(PermissionDenied):
            refresh_metric(
                organization=self.organization,
                actor=denied,
                metric_code="procurement_cycle_time",
                idempotency_key="denied",
            )
        with self.assertRaises(PermissionDenied):
            dashboard_results(organization=self.organization, actor=self.other_user)

        self.member.status = MembershipStatus.SUSPENDED
        self.member.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            dashboard_results(organization=self.organization, actor=self.user)
        self.member.status = MembershipStatus.ACTIVE
        self.member.save(update_fields=["status"])

        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            dashboard_results(organization=self.organization, actor=self.user)
        self.organization.status = OrganizationStatus.ACTIVE
        self.organization.save(update_fields=["status"])

    def test_05_platform_admin_has_no_implicit_tenant_access(self) -> None:
        platform = User.objects.create_user(username="p10-platform", password="x")
        PlatformRoleAssignment.objects.create(
            user=platform,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            assigned_by=self.user,
            approved_by=self.reviewer,
            reason="test platform separation",
        )
        with self.assertRaises(PermissionDenied):
            dashboard_results(organization=self.organization, actor=platform)

    def test_06_project_scope_filters_dashboard_results(self) -> None:
        scoped_user = User.objects.create_user(username="p10-scoped", password="x")
        self._grant(scoped_user, project=self.project_a)
        result_a = self._material_result()
        MetricResult.objects.filter(pk=result_a.pk).update(project=self.project_a)
        result_a.refresh_from_db()
        review_metric_result(
            result=result_a, reviewer=self.reviewer, reason="project A tie-out"
        )
        result_b = self._material_result()
        MetricResult.objects.filter(pk=result_b.pk).update(project=self.project_b)
        result_b.refresh_from_db()
        review_metric_result(
            result=result_b, reviewer=self.reviewer, reason="project B tie-out"
        )
        visible = dashboard_results(organization=self.organization, actor=scoped_user)
        self.assertEqual({item.project_id for item in visible}, {self.project_a.pk})

    def test_07_refresh_is_exactly_idempotent(self) -> None:
        first = self._refresh(key="same-refresh")
        second = self._refresh(key="same-refresh")
        self.assertEqual(first.pk, second.pk)

        replacement = self._refresh(key="replacement-refresh")
        first.refresh_from_db()
        self.assertEqual(first.freshness, MetricFreshness.STALE)
        self.assertEqual(replacement.replaces_id, first.pk)

    def test_08_idempotency_collision_fails_closed(self) -> None:
        self._refresh(key="collision")
        with self.assertRaises(ValidationError):
            refresh_metric(
                organization=self.organization,
                actor=self.user,
                metric_code="approved_budget",
                idempotency_key="collision",
            )

    def test_09_material_result_rejects_runner_self_review(self) -> None:
        result = self._material_result()
        self.assertNotIn(
            result,
            dashboard_results(organization=self.organization, actor=self.user),
        )
        with self.assertRaises(PermissionDenied):
            review_metric_result(result=result, reviewer=self.user, reason="self")

    def test_10_independent_review_is_immutable_and_idempotent(self) -> None:
        result = self._material_result()
        first = review_metric_result(
            result=result, reviewer=self.reviewer, reason="tie-out passed"
        )
        second = review_metric_result(
            result=result, reviewer=self.reviewer, reason="tie-out passed"
        )
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(ValidationError):
            review_metric_result(
                result=result, reviewer=self.reviewer, reason="changed"
            )

    def test_11_final_result_cannot_be_rewritten(self) -> None:
        result = self._refresh(key="immutable")
        result.value = {"average_seconds": 999}
        with self.assertRaises(ValidationError):
            result.save()
        definition = MetricDefinition.objects.get(code="approved_budget")
        definition.persian_name = "نام غیرمجاز"
        with self.assertRaises(ValidationError):
            definition.save()

    def test_12_drillthrough_requires_source_domain_permission(self) -> None:
        limited = User.objects.create_user(username="p10-limited", password="x")
        self._grant(limited, organization_scope=True, permissions=REPORTING_PERMISSIONS)
        result = self._refresh(key="source-denied")
        with self.assertRaises(PermissionDenied):
            drillthrough_manifest(
                organization=self.organization, actor=limited, result_id=str(result.pk)
            )

    def test_13_authorized_drillthrough_returns_manifest_without_writeback(
        self,
    ) -> None:
        result = self._refresh(key="source-allowed")
        before = Project.objects.count()
        visible = drillthrough_manifest(
            organization=self.organization, actor=self.user, result_id=str(result.pk)
        )
        self.assertEqual(visible.source_manifest["model"], "procurement.GoodsReceipt")
        self.assertEqual(Project.objects.count(), before)

    def test_14_export_is_scoped_idempotent_and_stores_no_bytes(self) -> None:
        self._refresh(key="for-export")
        first, content = export_dashboard_csv(
            organization=self.organization,
            actor=self.user,
            idempotency_key="export-key",
            purpose="acceptance",
        )
        second, retry_content = export_dashboard_csv(
            organization=self.organization,
            actor=self.user,
            idempotency_key="export-key",
            purpose="acceptance",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(content, retry_content)
        self.assertFalse(hasattr(first, "content"))
        self.assertEqual(MetricExportManifest.objects.count(), 1)

    def test_15_dashboard_is_rtl_jalali_and_private_non_cacheable(self) -> None:
        self._refresh(key="ui")
        self.client.force_login(self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("reporting:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "داشبورد شاخص‌های حاکم‌شده")
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")

    def test_16_refresh_and_export_have_no_source_mutation_and_are_audited(
        self,
    ) -> None:
        project_count = Project.objects.count()
        result = self._refresh(key="no-effects")
        export_dashboard_csv(
            organization=self.organization,
            actor=self.user,
            idempotency_key="no-effects-export",
            purpose="no effects",
        )
        self.assertEqual(Project.objects.count(), project_count)
        self.assertEqual(result.value["completed_cycles"], 0)
        self.assertIsNone(result.value["average_seconds"])
        self.assertEqual(result.freshness, MetricFreshness.INCOMPLETE)
        self.assertEqual(
            AuditEvent.objects.filter(action__startswith="reporting.").count(), 2
        )
        self.assertFalse(MetricResultReview.objects.filter(result=result).exists())
