"""CEP-067 source reconciliation and fail-closed reporting layer boundaries."""

import os
import re
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationStatus,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.projects.models import ProjectSite
from apps.reporting import test_p10_s02_s06 as fixture
from apps.reporting.models import (
    MetricDefinitionVersion,
    MetricFreshness,
    MetricRefreshRun,
    MetricResult,
    MetricRunStatus,
    MetricVersionStatus,
)
from apps.reporting.read_models import reporting_layers, require_result_scope
from apps.reporting.services import refresh_metric, review_metric_result


class ReportingLayersTests(TestCase):
    setUpTestData = classmethod(fixture.P10S02S06AcceptanceTests.setUpTestData.__func__)
    _grant = classmethod(fixture.P10S02S06AcceptanceTests._grant.__func__)

    def snapshot(
        self,
        *,
        code="procurement_cycle_time",
        project=None,
        complete=True,
        freshness=MetricFreshness.FRESH,
        review=False,
        scope=None,
    ):
        version = MetricDefinitionVersion.objects.get(
            definition__code=code, status="published"
        )
        now = timezone.now()
        run = MetricRefreshRun.objects.create(
            organization=self.organization,
            metric_version=version,
            project=project,
            status=MetricRunStatus.SUCCEEDED,
            idempotency_key=f"cep067-{MetricRefreshRun.objects.count()}",
            request_fingerprint="a" * 64,
            source_watermark="b" * 64,
            requested_by=self.user,
            started_at=now,
            finished_at=now,
        )
        result = MetricResult.objects.create(
            organization=self.organization,
            run=run,
            project=project,
            metric_code=code,
            value={"amount": "6754321.50"},
            currency="IRR",
            unit="money",
            as_of=now,
            freshness=freshness,
            coverage={"complete": complete, "source_count": 1},
            source_manifest=scope
            or {
                "model": "fixture.AuthoritativeSource",
                "ids": ["synthetic-source-v2"],
                "source_versions": [{"id": "synthetic-source", "version": 2}],
                "scope_kind": "project_set",
                "scope_project_ids": [str(project.pk)]
                if project
                else [str(self.project_a.pk), str(self.project_b.pk)],
            },
            calculation_hash="c" * 64,
        )
        if review:
            review_metric_result(
                result=result,
                reviewer=self.reviewer,
                reason="Synthetic independent review",
            )
        return result

    def model(self, actor=None, **kwargs):
        return reporting_layers(
            organization=self.organization, actor=actor or self.user, **kwargs
        )

    def page(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return self.client.get(reverse("reporting:dashboard"))

    def capture(self, name, response):
        if not (directory := os.environ.get("BONIRA_CEP067_CAPTURE_DIR")):
            return
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        content = re.sub(
            rb'name="csrfmiddlewaretoken" value="[^"]+"',
            b'name="csrfmiddlewaretoken" value="SYNTHETIC-EVIDENCE"',
            response.content,
        ).decode("utf-8")
        (output / f"{name}.html").write_text(
            "\n".join(line.rstrip() for line in content.splitlines()) + "\n",
            encoding="utf-8",
        )

    def test_four_layers_reconcile_exact_retained_source_and_version(self):
        result = self.snapshot(
            code="approved_budget", project=self.project_a, review=True
        )
        model = self.model()
        self.assertEqual(
            [layer.code for layer in model.layers],
            ["operational", "exception", "management", "executive"],
        )
        self.assertEqual(model.layers[1].cards, ())
        for index in (0, 2, 3):
            card = model.layers[index].cards[0]
            self.assertEqual(card.result.pk, result.pk)
            self.assertEqual(card.result.value, result.value)
            self.assertEqual(card.result.source_manifest, result.source_manifest)
            self.assertEqual(
                card.result.run.metric_version_id, result.run.metric_version_id
            )
            self.assertEqual(card.result.as_of, result.as_of)
            self.assertEqual(
                card.result.run.source_watermark, result.run.source_watermark
            )
        self.assertLessEqual(model.as_of, model.observed_at)

    def test_projection_executes_only_reads_and_does_not_refresh(self):
        self.snapshot()
        with CaptureQueriesContext(connection) as queries:
            self.model()
        self.assertTrue(queries)
        self.assertFalse(
            [
                q["sql"]
                for q in queries
                if re.search(r"\b(INSERT|UPDATE|DELETE)\b", q["sql"], re.IGNORECASE)
            ]
        )

    def test_latest_unreviewed_shadows_old_reviewed_values(self):
        self.snapshot(code="approved_budget", review=True)
        newest = self.snapshot(code="approved_budget")
        model = self.model()
        self.assertEqual(
            [card.result.pk for card in model.layers[0].cards], [newest.pk]
        )
        self.assertEqual(
            [card.result.pk for card in model.layers[1].cards], [newest.pk]
        )
        self.assertEqual(model.layers[2].cards, ())

    def test_latest_incomplete_and_stale_are_exceptions_without_values(self):
        self.snapshot()
        latest = self.snapshot(complete=False)
        self.snapshot(
            code="approved_budget", freshness=MetricFreshness.STALE, review=True
        )
        model = self.model()
        self.assertEqual(len(model.layers[0].cards), 2)
        self.assertEqual(len(model.layers[1].cards), 2)
        self.assertEqual(model.layers[2].cards, ())
        self.assertIn(latest.pk, [card.result.pk for card in model.layers[1].cards])
        response = self.page()
        self.assertNotContains(response, "6754321")
        self.capture("exceptions", response)

    def test_repeated_snapshots_are_selected_once_not_summed(self):
        for _ in range(3):
            newest = self.snapshot()
        cards = self.model().layers[2].cards
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].result.pk, newest.pk)
        self.assertEqual(cards[0].result.value["amount"], "6754321.50")

    def test_cutoff_uses_available_evidence_and_rejects_naive_or_future(self):
        old = self.snapshot()
        cutoff = timezone.now()
        self.snapshot()
        selected = self.model(as_of=cutoff).layers[0].cards
        self.assertEqual([card.result.pk for card in selected], [old.pk])
        for invalid in (cutoff.replace(tzinfo=None), cutoff + timedelta(days=1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.model(as_of=invalid)

    def test_source_native_incomplete_result_is_not_promoted(self):
        result = refresh_metric(
            organization=self.organization,
            actor=self.user,
            metric_code="actual_cost_coverage",
            idempotency_key="cep067-native-incomplete",
            project=self.project_a,
        )
        review_metric_result(
            result=result, reviewer=self.reviewer, reason="Coverage review"
        )
        model = self.model()
        self.assertEqual(
            model.layers[1].cards[0].result.source_manifest, result.source_manifest
        )
        self.assertEqual(model.layers[1].cards[0].result.value, {"amount": None})
        self.assertEqual(model.layers[2].cards, ())

    def test_project_scope_filters_before_grouping_and_direct_drill(self):
        viewer = User.objects.create_user(username="cep067-project", password="x")
        self._grant(viewer, project=self.project_a)
        allowed = self.snapshot(project=self.project_a)
        self.snapshot(project=self.project_b)
        aggregate = self.snapshot()
        cards = self.model(actor=viewer).layers[0].cards
        self.assertEqual([card.result.pk for card in cards], [allowed.pk])
        with self.assertRaises(PermissionDenied):
            require_result_scope(
                organization=self.organization, actor=viewer, result=aggregate
            )

    def test_unknown_scope_fails_closed_and_cannot_drill(self):
        result = self.snapshot(scope={"ids": []})
        self.assertEqual(self.model().layers[0].cards, ())
        with self.assertRaises(PermissionDenied):
            require_result_scope(
                organization=self.organization, actor=self.user, result=result
            )

    def test_foreign_tenant_result_and_source_project_are_denied(self):
        result = self.snapshot()
        with self.assertRaises(PermissionDenied):
            require_result_scope(
                organization=self.other_organization, actor=self.user, result=result
            )
        MetricResult.objects.filter(pk=result.pk).update(
            source_manifest={
                "scope_kind": "project_set",
                "scope_project_ids": ["unknown-foreign-id"],
            }
        )
        self.assertEqual(self.model().layers[0].cards, ())

    def test_revoked_source_permission_or_scope_and_cancelled_tenant_deny(self):
        self.snapshot()
        role = self.member.role_assignments.get().role
        permission = BusinessPermission.objects.get(code=P.PURCHASE_ORDERS_VIEW)
        role.permissions.remove(permission)
        self.assertEqual(self.model().layers[0].cards, ())
        role.permissions.add(permission)
        MembershipScopeGrant.objects.filter(membership=self.member).delete()
        with self.assertRaises(PermissionDenied):
            self.model()
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.model()

    def test_executive_permission_does_not_grant_sources(self):
        viewer = User.objects.create_user(username="cep067-executive", password="x")
        self._grant(
            viewer, organization_scope=True, permissions=fixture.REPORTING_PERMISSIONS
        )
        self.snapshot()
        self.assertEqual(self.model(actor=viewer).layers[3].cards, ())
        role = self.member.role_assignments.get().role
        role.permissions.remove(
            BusinessPermission.objects.get(code=P.REPORTING_PORTFOLIO_VIEW)
        )
        model = self.model()
        self.assertFalse(model.layers[3].available)
        self.assertTrue(model.layers[2].cards)

    def test_sensitive_result_requires_separate_permission(self):
        result = self.snapshot()
        definition = result.run.metric_version.definition
        type(definition).objects.filter(pk=definition.pk).update(
            sensitivity="sensitive"
        )
        role = self.member.role_assignments.get().role
        role.permissions.remove(
            BusinessPermission.objects.get(
                code=P.REPORTING_METRIC_RESULT_VIEW_SENSITIVE
            )
        )
        self.assertEqual(self.model().layers[0].cards, ())

    def test_model_evidence_immutable_and_ui_has_four_layers_no_new_metrics(self):
        result = self.snapshot(
            code="approved_budget", project=self.project_a, review=True
        )
        result.value = {"amount": "999"}
        with self.assertRaises(ValidationError):
            result.save()
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        for code in ("operational", "exception", "management", "executive"):
            self.assertContains(response, f'id="reporting-{code}"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "زمان مبنای منبع")
        self.assertContains(response, "نسخه شاخص")
        for invented in ("CPI", "SPI", "EVM", "liquidity_score"):
            self.assertNotContains(response, invented)
        self.capture("ready", response)

    def test_empty_neutral_and_unauthenticated_views(self):
        self.assertEqual(
            self.client.get(reverse("reporting:dashboard")).status_code, 302
        )
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نتیجه واجد شرایطی")
        self.capture("empty", response)

    def test_site_only_grant_cannot_expand_to_parent_project_aggregate(self):
        viewer = User.objects.create_user(username="cep067-site", password="x")
        membership = self._grant(viewer, project=self.project_a)
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project_a,
            code="CEP067-SITE",
            name="Synthetic site",
            created_by=self.user,
            updated_by=self.user,
        )
        MembershipScopeGrant.objects.filter(membership=membership).update(
            scope_type=AuthorizationScopeType.SITE, site=site
        )
        self.snapshot(project=self.project_a)
        self.assertEqual(self.model(actor=viewer).layers[0].cards, ())

    def test_superseded_definition_is_not_a_current_metric(self):
        result = self.snapshot()
        MetricDefinitionVersion.objects.filter(pk=result.run.metric_version_id).update(
            status=MetricVersionStatus.SUPERSEDED
        )
        self.assertEqual(self.model().layers[0].cards, ())

    def test_organization_metric_requires_organization_scope(self):
        viewer = User.objects.create_user(username="cep067-no-org", password="x")
        self._grant(viewer, project=self.project_a)
        result = self.snapshot(
            code="cleared_cash_position",
            review=True,
            scope={"scope_kind": "organization", "ids": ["synthetic-clearing"]},
        )
        self.assertEqual(self.model(actor=viewer).layers[0].cards, ())
        self.assertEqual(self.model().layers[2].cards[0].result.pk, result.pk)

    def test_direct_url_rechecks_full_scope_and_uses_neutral_denial(self):
        viewer = User.objects.create_user(username="cep067-url", password="x")
        self._grant(viewer, project=self.project_a)
        aggregate = self.snapshot()
        self.client.force_login(viewer)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("reporting:drillthrough", args=[aggregate.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"synthetic-source-v2", response.content)
