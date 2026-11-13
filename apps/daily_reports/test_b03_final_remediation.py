"""Bounded regressions for BON-DEF-0017, 0018 and 0019."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.audit.models import AuditAction, AuditEvent
from apps.daily_reports.field_models import FieldDownstreamProposal
from apps.daily_reports.field_services import (
    create_field_observation,
    create_field_proposal,
    review_field_observation,
    start_field_observation_review,
    submit_field_observation,
    submit_field_proposal,
)
from apps.daily_reports.models import DailyReportLaborEntry
from apps.daily_reports.services import (
    _approve_daily_report_domain,
    add_daily_report_labor_entry,
    approve_daily_report,
    create_daily_report,
    submit_daily_report,
)
from apps.workflows.models import WorkItem
from apps.workflows.runtime import claim_work_item, complete_work_item
from tests.test_b02_remediation import B02Fixture


class FinalFixture(B02Fixture):
    def setUp(self):
        self.make_fixture()
        self.checker, _, _ = self.member(
            "final-checker",
            [
                "daily_reports.view", "daily_reports.approve",
                "field_observations.view", "field_observations.review",
                "field_proposals.review", "work_items.view",
                "work_items.claim", "work_items.act",
            ],
            site=self.site,
        )
        self.report = create_daily_report(
            organization=self.organization, actor=self.owner, project=self.project,
            site=self.site, reporting_date=date(2026, 11, 10),
            work_performed="B03 final focused fixture",
        )

    def labor(self, **changes):
        data = {
            "organization": self.organization, "actor": self.owner,
            "report_id": self.report.pk, "team_name": "Crew", "worker_count": 4,
            "hours_worked": Decimal("6.50"), "notes": "Synthetic",
        }
        data.update(changes)
        return add_daily_report_labor_entry(**data)

    def proposal(self):
        obs = create_field_observation(
            organization=self.organization, actor=self.owner,
            project=self.project, site=self.site, kind="general",
            title="B03 final proposal", operation_key=uuid4(),
        )
        submit_field_observation(
            organization=self.organization, actor=self.owner,
            observation_id=obs.pk, operation_key=uuid4(),
        )
        start_field_observation_review(
            organization=self.organization, actor=self.checker,
            observation_id=obs.pk, operation_key=uuid4(),
        )
        review_field_observation(
            organization=self.organization, actor=self.checker,
            observation_id=obs.pk, accepted=True, reason="", operation_key=uuid4(),
        )
        proposal = create_field_proposal(
            organization=self.organization, actor=self.owner, observation_id=obs.pk,
            family="progress", lines=[{"quantity": "2"}], operation_key=uuid4(),
        )
        submit_field_proposal(
            organization=self.organization, actor=self.owner,
            proposal_id=proposal.pk, operation_key=uuid4(),
        )
        return proposal


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class B03FinalRemediationTests(FinalFixture, TestCase):
    def test_author_direct_post_and_domain_approval_denied_without_history_change(self):
        submit_daily_report(
            organization=self.organization, actor=self.owner, report_id=self.report.pk
        )
        self.login(self.owner)
        url = reverse("daily_reports:approve", args=[self.report.pk])
        detail = reverse("daily_reports:detail", args=[self.report.pk])
        self.assertNotContains(self.client.get(detail), f'action="{url}"')
        before = list(WorkItem.objects.values("id", "status", "current_assignee_id"))
        self.client.post(url)
        with self.assertRaises(PermissionDenied):
            _approve_daily_report_domain(
                organization=self.organization, actor=self.owner,
                report_id=self.report.pk,
            )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "submitted")
        self.assertEqual(before, list(WorkItem.objects.values(
            "id", "status", "current_assignee_id"
        )))
        self.assertFalse(AuditEvent.objects.filter(
            entity_id=str(self.report.pk), action=AuditAction.DAILY_REPORT_APPROVED
        ).exists())
        approve_daily_report(
            organization=self.organization, actor=self.checker,
            report_id=self.report.pk,
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.approved_by_id, self.checker.pk)

    def test_shared_workbench_author_cannot_bypass_domain_guard(self):
        submit_daily_report(
            organization=self.organization, actor=self.owner, report_id=self.report.pk
        )
        item = WorkItem.objects.get(instance__subject_id=self.report.pk)
        with self.assertRaises(PermissionDenied):
            claim_work_item(
                actor=self.owner, organization=self.organization,
                work_item_id=item.pk, idempotency_key="final-author-claim",
            )
        before = AuditEvent.objects.count()
        with self.assertRaises(PermissionDenied):
            complete_work_item(
                actor=self.owner, organization=self.organization,
                work_item_id=item.pk, outcome="approved",
                idempotency_key="final-author-complete",
            )
        item.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(item.status, "open")
        self.assertEqual(self.report.status, "submitted")
        self.assertEqual(AuditEvent.objects.count(), before)

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_full_erp_existing_compatibility_contract_preserved(self):
        submit_daily_report(
            organization=self.organization, actor=self.owner, report_id=self.report.pk
        )
        result = approve_daily_report(
            organization=self.organization, actor=self.owner, report_id=self.report.pk
        )
        self.assertEqual(result.status, "approved")

    def test_labor_replay_conflict_intentional_duplicate_and_finalized_retry(self):
        key = uuid4()
        first = self.labor(operation_key=key)
        self.assertEqual(self.labor(operation_key=key).pk, first.pk)
        with self.assertRaises(ValueError):
            self.labor(operation_key=key, worker_count=5)
        second = self.labor(operation_key=uuid4())
        self.assertNotEqual(first.pk, second.pk)
        submit_daily_report(
            organization=self.organization, actor=self.owner, report_id=self.report.pk
        )
        self.assertEqual(self.labor(operation_key=key).pk, first.pk)
        with self.assertRaises(ValueError):
            self.labor(operation_key=uuid4())
        self.assertEqual(DailyReportLaborEntry.objects.filter(report=self.report).count(), 2)
        self.assertEqual(AuditEvent.objects.filter(
            action=AuditAction.DAILY_REPORT_LABOR_ADDED,
            entity_id__in=[str(first.pk), str(second.pk)],
        ).count(), 2)

    def test_labor_replay_still_requires_current_permission_and_scope(self):
        key = uuid4()
        self.labor(operation_key=key)
        wrong, _, _ = self.member(
            "final-wrong", ["daily_reports.add_labor", "daily_reports.approve"],
            site=self.sibling,
        )
        with self.assertRaises(PermissionDenied):
            self.labor(operation_key=key, actor=wrong)
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.labor(operation_key=key)

    def test_labor_http_requires_request_identity_and_retains_it_on_invalid_form(self):
        self.login(self.owner)
        url = reverse("daily_reports:labor_add", args=[self.report.pk])
        values = {"team_name": "Crew", "worker_count": 4, "hours_worked": "6.50", "notes": ""}
        self.assertEqual(self.client.post(url, values).status_code, 200)
        self.assertFalse(self.report.labor_entries.exists())
        key = str(uuid4())
        values.update(operation_key=key, hours_worked="9999999999")
        response = self.client.post(url, values)
        self.assertContains(response, key)
        self.assertFalse(self.report.labor_entries.exists())
        values["hours_worked"] = "6.50"
        self.client.post(url, values)
        self.client.post(url, values)
        self.assertEqual(self.report.labor_entries.count(), 1)

    def test_proposal_ui_independence_reason_replay_and_context(self):
        proposal = self.proposal()
        detail = reverse("daily_reports:field_observation_detail", args=[proposal.observation_id])
        accept = reverse("daily_reports:field_proposal_review", args=[proposal.observation_id, proposal.pk, "accept"])
        reject = reverse("daily_reports:field_proposal_review", args=[proposal.observation_id, proposal.pk, "reject"])
        self.login(self.owner)
        self.assertNotContains(self.client.get(detail), f'action="{accept}"')
        self.login(self.checker)
        response = self.client.get(detail)
        self.assertContains(response, f'action="{accept}"')
        self.assertContains(response, f'action="{reject}"')
        self.assertContains(response, f'proposal-{proposal.pk}-reason')
        key = str(uuid4())
        self.client.post(reject, {"operation_key": key, "reason": ""})
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "submitted")
        values = {"operation_key": key, "reason": "Correction required"}
        self.client.post(reject, values)
        self.client.post(reject, values)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "rejected")
        self.assertEqual(proposal.reviewed_by_id, self.checker.pk)
        self.assertEqual(proposal.transitions.filter(to_status="rejected").count(), 1)
        self.assertNotContains(self.client.get(detail), f'action="{accept}"')
        invalid_context = reverse("daily_reports:field_proposal_review", args=[uuid4(), proposal.pk, "accept"])
        self.assertIn(self.client.post(invalid_context, values).status_code, (403, 404))

    def test_proposal_viewer_and_sibling_reviewer_cannot_see_or_execute_review(self):
        proposal = self.proposal()
        detail = reverse("daily_reports:field_observation_detail", args=[proposal.observation_id])
        accept = reverse("daily_reports:field_proposal_review", args=[proposal.observation_id, proposal.pk, "accept"])
        viewer, _, _ = self.member("final-viewer", ["field_observations.view"], site=self.site)
        self.login(viewer)
        self.assertNotContains(self.client.get(detail), f'action="{accept}"')
        self.assertEqual(self.client.post(accept, {"operation_key": uuid4()}).status_code, 403)
        wrong, _, _ = self.member("final-sibling", ["field_observations.view", "field_proposals.review"], site=self.sibling)
        self.login(wrong)
        response = self.client.post(accept, {"operation_key": uuid4()}, follow=True)
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(FieldDownstreamProposal.objects.get(pk=proposal.pk).status, "submitted")

    def test_review_post_keeps_existing_review_only_permission_contract(self):
        proposal = self.proposal()
        reviewer, _, _ = self.member(
            "final-review-only", ["field_proposals.review"], site=self.site
        )
        self.login(reviewer)
        detail = reverse("daily_reports:field_observation_detail", args=[proposal.observation_id])
        self.assertEqual(self.client.get(detail).status_code, 403)
        context = create_field_observation(
            organization=self.organization, actor=self.owner,
            project=self.project, site=self.site, kind="general",
            title="Separate same-site observation", operation_key=uuid4(),
        )
        wrong_url = reverse("daily_reports:field_proposal_review", args=[context.pk, proposal.pk, "accept"])
        self.assertEqual(self.client.post(wrong_url, {"operation_key": uuid4()}).status_code, 404)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "submitted")
        url = reverse("daily_reports:field_proposal_review", args=[proposal.observation_id, proposal.pk, "accept"])
        self.assertEqual(self.client.post(url, {"operation_key": uuid4()}).status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "accepted")
        self.assertEqual(proposal.reviewed_by_id, reviewer.pk)


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class B03LaborConcurrencyTests(FinalFixture, TransactionTestCase):
    # The historical PostgreSQL template retains tables outside the active app
    # registry. Django's scoped flush cascades their FKs in this disposable DB.
    available_apps = [config.name for config in apps.get_app_configs()]  # noqa: RUF012

    def test_concurrent_same_logical_request_creates_one_row_and_one_audit(self):
        barrier = Barrier(2)
        key = uuid4()

        def invoke():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.labor(operation_key=key).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(invoke) for _ in range(2)]
            ids = [future.result(timeout=30) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(self.report.labor_entries.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            organization=self.organization, action=AuditAction.DAILY_REPORT_LABOR_ADDED,
            correlation_id=key,
        ).count(), 1)
