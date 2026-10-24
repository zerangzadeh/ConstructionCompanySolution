"""Focused regressions for the nine approved Stage 3A presentation decisions."""

import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch
from uuid import uuid4

from django import forms
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.http import QueryDict
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.compliance.forms import TemplatePublishForm
from apps.documents.models import Document, DocumentVersion
from apps.equipment.cost_services import (
    finalize_cost_allocation,
    prepare_cost_allocation,
    prepare_cost_handoff,
    reverse_cost_allocation,
)
from apps.equipment.forms import (
    CostAllocationForm,
    CostAllocationReversalForm,
    CostHandoffForm,
    FuelForm,
    MeterReadingForm,
    UsageForm,
)
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import (
    EquipmentCostAllocation,
    EquipmentCostPolicyVersion,
    EquipmentCostRate,
    EquipmentCostSourceEnvelope,
    EquipmentMeter,
    EquipmentUsageLog,
    FuelLog,
    MeterReading,
)
from apps.equipment.p8_services import record_fuel, record_meter_reading, record_usage
from apps.knowledge.forms import RecurrenceForm, ReuseForm, SourceForm
from apps.knowledge.reference_ui import visible_references
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.payroll.forms import OrganizationForm, ReversalForm, StatutoryExportForm
from apps.projects.models import Project, ProjectCostFact, ProjectDocumentLink
from apps.reporting.closeout_ui import CloseoutEvidenceForm
from apps.reporting.project_closeout import (
    create_closeout_case,
    run_closeout_assessment,
)
from apps.support.models import SupportCase
from apps.workforce.forms import PerformanceEvaluationForm
from core.home import HomeLink
from core.ui_forms import OccurrenceKeyWidget, StructuredDataWidget


class PresentationContractsTests(SimpleTestCase):
    def test_home_prioritizes_existing_tasks_and_alerts_without_business_summaries(
        self,
    ):
        html = render_to_string(
            "home.html",
            {
                "home_state": "normal",
                "home_organization": SimpleNamespace(name="Context"),
                "home_workspaces": [
                    HomeLink("Projects", "projects:list", "projects.view")
                ],
                "home_assigned_work": HomeLink(
                    "Assigned", "workflows:workbench", "work_items.view"
                ),
                "home_alerts": HomeLink(
                    "Alerts", "support:notifications", "support.notifications_view"
                ),
            },
        )
        self.assertLess(
            html.index('id="home-start-work"'), html.index('id="home-workspaces"')
        )
        self.assertIn(reverse("workflows:workbench"), html)
        self.assertIn(reverse("support:notifications"), html)

    def test_structured_editors_accept_existing_nested_types_without_schema(self):
        payload = {
            "custom": [1, True, None, {"evidence": "مستند"}],
            "old_key": "unchanged",
        }
        form = PerformanceEvaluationForm(organization=uuid4())
        self.assertIsInstance(
            form.fields["criteria_snapshot"].widget, StructuredDataWidget
        )
        self.assertEqual(
            form.fields["criteria_snapshot"].clean(json.dumps(payload)), payload
        )
        publication = TemplatePublishForm()
        for name in ("checklist", "required_evidence", "source_references"):
            self.assertIsInstance(publication.fields[name].widget, StructuredDataWidget)
            self.assertEqual(
                publication.fields[name].clean(json.dumps([payload])), [payload]
            )
        self.assertEqual(
            publication.fields["outcome_rules"].clean(json.dumps(payload)), payload
        )

    def test_payroll_evidence_uses_same_object_contract(self):
        class EvidenceForm(OrganizationForm):
            evidence_json = forms.CharField(required=False)

        form = EvidenceForm(organization=uuid4())
        self.assertIsInstance(form.fields["evidence_json"].widget, StructuredDataWidget)
        self.assertIn("structured-data.js", str(form.media))

    def test_widget_escapes_untrusted_content_and_compiles_all_affected_templates(self):
        self.assertIsNotNone(finders.find("js/structured-data.js"))
        self.assertIsNotNone(finders.find("js/reference-rows.js"))
        html = StructuredDataWidget().render(
            "evidence", "</textarea><script>alert(1)</script>"
        )
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;/textarea&gt;", html)
        for name in (
            "home.html",
            "reporting/project_closeout_detail.html",
            "payroll/form.html",
            "workforce/foundation_form.html",
            "compliance/form.html",
            "equipment/form.html",
            "knowledge/recurrence.html",
            "knowledge/candidate_detail.html",
            "knowledge/publication_detail.html",
        ):
            get_template(name)

    def test_manual_occurrence_keys_are_stable_on_validation_and_distinct_for_new_forms(
        self,
    ):
        for form_class in (MeterReadingForm, UsageForm, FuelForm, CostAllocationForm):
            first = form_class(organization=uuid4())
            key = first.initial["source_key"]
            self.assertNotEqual(
                key, form_class(organization=uuid4()).initial["source_key"]
            )
            bound = form_class({"source_key": key}, organization=uuid4())
            self.assertFalse(bound.is_valid())
            self.assertEqual(bound["source_key"].value(), key)
            self.assertIn(f'value="{key}"', str(bound["source_key"]))
            missing = form_class({}, organization=uuid4())
            self.assertNotIn("source_key", missing.initial)

    def test_existing_source_keys_remain_exact_and_explicit_override_is_supported(self):
        widget = OccurrenceKeyWidget()
        self.assertEqual(
            widget.value_from_datadict(
                {"source_key": "original-key"}, {}, "source_key"
            ),
            "original-key",
        )
        self.assertEqual(
            widget.value_from_datadict(
                {"source_key": "generated", "source_key_existing": "external:123"},
                {},
                "source_key",
            ),
            "external:123",
        )
        reversal = CostAllocationReversalForm({"reason": "correction"})
        self.assertTrue(reversal.is_valid())
        self.assertEqual(reversal.cleaned_data["reversal_source_key"], "")

    def test_payroll_retry_keys_and_supplied_external_correlation_survive(self):
        first = ReversalForm()
        key = first.initial["idempotency_key"]
        self.assertTrue(first.fields["idempotency_key"].widget.is_hidden)
        invalid = ReversalForm({"idempotency_key": key})
        self.assertFalse(invalid.is_valid())
        self.assertEqual(invalid["idempotency_key"].value(), key)
        export = StatutoryExportForm()
        base = {
            "idempotency_key": export.initial["idempotency_key"],
            "status": export.fields["status"].choices[0][0],
            "artifact_name": "evidence.json",
        }
        internal = StatutoryExportForm(base)
        self.assertTrue(internal.is_valid(), internal.errors)
        self.assertEqual(
            internal.cleaned_data["correlation_id"], base["idempotency_key"]
        )
        supplied = StatutoryExportForm(
            {**base, "correlation_id": "provider-reference-42"}
        )
        self.assertTrue(supplied.is_valid(), supplied.errors)
        self.assertEqual(
            supplied.cleaned_data["correlation_id"], "provider-reference-42"
        )


class DiscoveryBoundaryTests(TestCase):
    def test_manual_operation_forms_keep_retry_identity_with_real_services(self):
        self.role.permissions.set(BusinessPermission.objects.all())
        equipment = Equipment.objects.create(
            organization=self.organization,
            code="S3A-EQ",
            name="Test equipment",
            category="test",
        )
        meter = EquipmentMeter.objects.create(
            organization=self.organization,
            equipment=equipment,
            kind="hours",
            name="Hours",
            unit="hour",
            created_by=self.actor,
        )
        now = timezone.now()
        cases = [
            (
                MeterReadingForm,
                record_meter_reading,
                MeterReading,
                {"meter": str(meter.pk), "value": "10", "observed_at": now.isoformat()},
            ),
            (
                UsageForm,
                record_usage,
                EquipmentUsageLog,
                {
                    "equipment": str(equipment.pk),
                    "started_at": (now - timedelta(hours=1)).isoformat(),
                    "ended_at": now.isoformat(),
                    "runtime_hours": "1",
                },
            ),
            (
                FuelForm,
                record_fuel,
                FuelLog,
                {
                    "equipment": str(equipment.pk),
                    "occurred_at": now.isoformat(),
                    "quantity": "10",
                    "unit": "litre",
                },
            ),
        ]
        for form_class, service, model, payload in cases:
            key = form_class(organization=self.organization).initial["source_key"]
            bound = form_class(
                {**payload, "source_key": key}, organization=self.organization
            )
            self.assertTrue(bound.is_valid(), bound.errors)
            first = service(
                organization=self.organization, actor=self.actor, **bound.cleaned_data
            )
            retry = service(
                organization=self.organization, actor=self.actor, **bound.cleaned_data
            )
            self.assertEqual(first.pk, retry.pk)
            self.assertEqual(
                model.objects.filter(organization=self.organization).count(), 1
            )
            next_key = form_class(organization=self.organization).initial["source_key"]
            fresh = form_class(
                {**payload, "source_key": next_key}, organization=self.organization
            )
            self.assertTrue(fresh.is_valid(), fresh.errors)
            separate = service(
                organization=self.organization, actor=self.actor, **fresh.cleaned_data
            )
            self.assertNotEqual(first.pk, separate.pk)

    def test_cost_form_retry_handoff_and_default_reversal_preserve_financial_authority(
        self,
    ):
        self.role.permissions.set(BusinessPermission.objects.all())
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.other,
            role="member",
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=self.role,
            reason="Explicit independent reviewer",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Focused test scope",
        )
        equipment = Equipment.objects.create(
            organization=self.organization,
            code="S3A-COST",
            name="Test cost equipment",
            category="test",
        )
        now = timezone.now()
        deployment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=equipment,
            project=self.project,
            start_date=now.date() - timedelta(days=1),
            status="active",
        )
        policy = EquipmentCostPolicyVersion.objects.create(
            organization=self.organization,
            code="S3A-TEST",
            version=1,
            status="published",
            effective_from=deployment.start_date,
            monetary_policy_code="test-fixture",
            monetary_policy_version="v1",
            prepared_by=self.actor,
        )
        EquipmentCostRate.objects.create(
            organization=self.organization,
            policy=policy,
            equipment=equipment,
            rate_amount=Decimal(10),
            component_snapshot={"fixture": "10"},
            effective_from=deployment.start_date,
            prepared_by=self.actor,
        )
        usage = record_usage(
            organization=self.organization,
            actor=self.actor,
            equipment=equipment,
            deployment=deployment,
            started_at=now - timedelta(hours=1),
            ended_at=now,
            runtime_hours=Decimal(1),
            source_key="stage3a-cost-usage",
        )
        initial_counts = (JournalEntry.objects.count(), ProjectCostFact.objects.count())
        key = CostAllocationForm(organization=self.organization).initial["source_key"]
        form = CostAllocationForm(
            {"usage": str(usage.pk), "source_key": key}, organization=self.organization
        )
        self.assertTrue(form.is_valid(), form.errors)
        allocation = prepare_cost_allocation(
            organization=self.organization, actor=self.actor, **form.cleaned_data
        )
        retry = prepare_cost_allocation(
            organization=self.organization, actor=self.actor, **form.cleaned_data
        )
        self.assertEqual(allocation.pk, retry.pk)
        with self.assertRaises(ValueError):
            finalize_cost_allocation(
                organization=self.organization, actor=self.actor, allocation=allocation
            )
        finalize_cost_allocation(
            organization=self.organization, actor=self.other, allocation=allocation
        )
        for attempt in range(2):
            handoff = CostHandoffForm(
                {"allocation": str(allocation.pk)}, organization=self.organization
            )
            self.assertTrue(handoff.is_valid(), handoff.errors)
            envelope = prepare_cost_handoff(
                organization=self.organization, actor=self.actor, **handoff.cleaned_data
            )
            if attempt == 0:
                first_envelope_id = envelope.pk
            self.assertEqual(first_envelope_id, envelope.pk)
        self.assertEqual(
            EquipmentCostSourceEnvelope.objects.filter(allocation=allocation).count(), 1
        )
        reversal = CostAllocationReversalForm({"reason": "Test correction"})
        self.assertTrue(reversal.is_valid(), reversal.errors)
        inverse = reverse_cost_allocation(
            organization=self.organization,
            actor=self.actor,
            allocation=allocation,
            **reversal.cleaned_data,
        )
        reverse_retry = reverse_cost_allocation(
            organization=self.organization,
            actor=self.actor,
            allocation=allocation,
            **reversal.cleaned_data,
        )
        self.assertEqual(inverse.pk, reverse_retry.pk)
        self.assertEqual(inverse.source_key, f"reverse:{key}")
        self.assertEqual(inverse.amount, -allocation.amount)
        self.assertEqual(
            EquipmentCostAllocation.objects.filter(
                organization=self.organization
            ).count(),
            2,
        )
        self.assertEqual(
            initial_counts,
            (JournalEntry.objects.count(), ProjectCostFact.objects.count()),
        )

    def test_closeout_ui_and_post_pin_exact_authorized_versions_with_custom_compatibility(
        self,
    ):
        self.role.permissions.set(BusinessPermission.objects.all())
        case = create_closeout_case(
            organization=self.organization,
            actor=self.actor,
            project=self.project,
            operation_key="stage3a-case",
        )
        document, versions = self.document("Visible closeout evidence")
        _, denied_versions = self.document("Hidden unlinked evidence", linked=False)
        self.client.force_login(self.actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        url = reverse("reporting:project_closeout_evidence", args=[case.pk])
        with patch.object(
            DocumentVersion,
            "is_available",
            new_callable=PropertyMock,
            return_value=True,
        ):
            response = self.client.post(
                url,
                {
                    "document_version_id": str(versions[0].pk),
                    "purpose": "closeout_support",
                },
            )
            self.assertEqual(response.status_code, 302)
            link = case.evidence_links.get()
            self.assertEqual(link.document_version_id, versions[0].pk)
            self.assertEqual(link.document_hash, versions[0].sha256)
            self.client.post(
                url,
                {
                    "document_version_id": str(versions[0].pk),
                    "evidence_role": "legacy-role",
                },
            )
            self.assertEqual(case.evidence_links.count(), 2)
            self.client.post(
                url,
                {
                    "document_version_id": str(denied_versions[0].pk),
                    "purpose": "closeout_support",
                },
            )
            self.assertEqual(case.evidence_links.count(), 2)
            detail = self.client.get(
                reverse("reporting:project_closeout_detail", args=[case.pk])
            )
            self.assertEqual(detail.status_code, 200)
            self.assertContains(detail, document.title)
            self.assertContains(detail, 'id="closeout-evidence-title"')
            self.assertNotContains(detail, "Hidden unlinked evidence")
            run_closeout_assessment(
                case=case,
                actor=self.actor,
                idempotency_key="stage3a-assess",
                cutoff_at=timezone.now(),
                expected_revision=case.revision,
            )
            assessed = self.client.get(
                reverse("reporting:project_closeout_detail", args=[case.pk])
            )
            self.assertContains(assessed, "هویت و دامنه پروژه")
            self.assertContains(assessed, "دامنه مسئول منبع")
            self.assertContains(assessed, "در قرارداد منبع ارائه نشده است")
            self.assertContains(assessed, "جزئیات فنی و حسابرسی")
            self.role.permissions.remove(
                BusinessPermission.objects.get(
                    code=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_SENSITIVE_VIEW
                )
            )
            masked = self.client.get(
                reverse("reporting:project_closeout_detail", args=[case.pk])
            )
            case.refresh_from_db()
            for item in case.current_assessment.items.exclude(sensitivity="normal"):
                self.assertNotContains(masked, item.source_hash)
            self.assertContains(masked, "ماسک‌شده")

    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user(username="stage3a-actor")
        cls.other = User.objects.create_user(username="stage3a-other")
        cls.outsider = User.objects.create_user(username="stage3a-outsider")
        cls.organization = Organization.objects.create(name="Stage3A", slug="stage3a")
        cls.foreign = Organization.objects.create(
            name="Foreign", slug="stage3a-foreign"
        )
        membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.actor,
            role="member",
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        cls.role = OrganizationRole.objects.create(
            organization=cls.organization,
            code="stage3a",
            name="Stage3A",
            created_by=cls.actor,
            updated_by=cls.actor,
        )
        cls.role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.SUPPORT_CASE_VIEW,
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.PROJECTS_VIEW,
                ]
            )
        )
        MembershipRoleAssignment.objects.create(
            organization=cls.organization,
            membership=membership,
            role=cls.role,
            reason="Focused presentation test",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Focused presentation test",
        )
        cls.own_case = SupportCase.objects.create(
            organization=cls.organization,
            requester=cls.actor,
            summary="Own resolved case",
            status="resolved",
            category="general",
        )
        cls.other_case = SupportCase.objects.create(
            organization=cls.organization,
            requester=cls.other,
            summary="Private other requester",
            status="resolved",
            category="general",
        )
        cls.foreign_case = SupportCase.objects.create(
            organization=cls.foreign,
            requester=cls.actor,
            summary="Foreign case",
            status="resolved",
            category="general",
        )
        cls.active_case = SupportCase.objects.create(
            organization=cls.organization,
            requester=cls.actor,
            summary="Own open case",
            status="open",
            category="general",
        )
        cls.project = Project.objects.create(
            organization=cls.organization, code="S3A", name="Stage3A project"
        )

    def references(self, **kwargs):
        return visible_references(
            organization=self.organization, actor=self.actor, **kwargs
        )

    def test_source_discovery_respects_requester_tenant_state_and_permission(self):
        groups, references = self.references()
        self.assertEqual({row["id"] for row in references.values()}, {self.own_case.pk})
        self.assertNotIn(self.other_case.summary, str(groups))
        self.assertNotIn(self.foreign_case.summary, str(groups))
        self.role.permissions.clear()
        self.assertEqual(self.references(), ([], {}))
        self.assertEqual(
            visible_references(organization=self.organization, actor=self.outsider),
            ([], {}),
        )

    def test_consumer_discovery_retains_nonfinal_consumers_without_broadening_access(
        self,
    ):
        _, references = self.references(sources=False)
        self.assertEqual(
            {row["id"] for row in references.values()},
            {self.own_case.pk, self.active_case.pk},
        )

    def test_selector_derives_source_identity_and_rejects_forged_or_stale_choice(self):
        _, references = self.references()
        key = next(iter(references))
        form = SourceForm(
            {"reference": key, "citation_purpose": "review"},
            organization=self.organization,
            actor=self.actor,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data,
            {
                "source_type": "support_case",
                "source_id": self.own_case.pk,
                "citation_purpose": "review",
            },
        )
        invalid = SourceForm(
            {
                "reference": key.replace(
                    str(self.own_case.pk), str(self.other_case.pk)
                ),
                "citation_purpose": "review",
            },
            organization=self.organization,
            actor=self.actor,
        )
        self.assertFalse(invalid.is_valid())
        consumer = ReuseForm(organization=self.organization, actor=self.actor)
        data = {
            "reference": key,
            "reuse_type": consumer.fields["reuse_type"].choices[0][0],
            "purpose": "review",
        }
        bound = ReuseForm(data, organization=self.organization, actor=self.actor)
        self.assertTrue(bound.is_valid(), bound.errors)
        self.assertEqual(
            bound.cleaned_data["consumer_version"], str(self.own_case.created_at)
        )
        stale = ReuseForm(
            {**data, "reference": key + "stale"},
            organization=self.organization,
            actor=self.actor,
        )
        self.assertFalse(stale.is_valid())

    def test_legacy_id_based_reference_submissions_remain_compatible(self):
        form = SourceForm(
            {
                "source_type": "support_case",
                "source_id": str(self.own_case.pk),
                "citation_purpose": "review",
            },
            organization=self.organization,
            actor=self.actor,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("reference", form.cleaned_data)

    def test_structured_recurrence_rows_map_to_original_payload_and_reject_forgery(
        self,
    ):
        data = QueryDict(mutable=True)
        data.update(
            recurrence_key="REC",
            scope_description="review",
            period_start="2026-10-01",
            period_end="2026-10-24",
            sources_rows_present="1",
        )
        data.setlist("sources_rows", [f"support_case,{self.own_case.pk}"])
        form = RecurrenceForm(data, organization=self.organization, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["sources"],
            [{"source_type": "support_case", "source_id": str(self.own_case.pk)}],
        )
        self.assertIn("data-reference-rows", str(form["sources"]))
        data.setlist("sources_rows", [f"support_case,{self.other_case.pk}"])
        self.assertFalse(
            RecurrenceForm(
                data, organization=self.organization, actor=self.actor
            ).is_valid()
        )

    def test_handoff_reuses_existing_identity_and_preserves_supplied_identity(self):
        allocation = SimpleNamespace(pk=uuid4())
        form = CostHandoffForm(
            {"allocation": str(allocation.pk)}, organization=self.organization
        )
        form.fields["allocation"].clean = lambda value: allocation
        with patch(
            "apps.equipment.forms.EquipmentCostSourceEnvelope.objects.filter"
        ) as query:
            query.return_value.first.return_value = SimpleNamespace(
                occurrence_key="existing-proposal"
            )
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["occurrence_key"], "existing-proposal")
        supplied = CostHandoffForm(
            {"allocation": str(allocation.pk), "occurrence_key": "external-proposal"},
            organization=self.organization,
        )
        supplied.fields["allocation"].clean = lambda value: allocation
        self.assertTrue(supplied.is_valid(), supplied.errors)
        self.assertEqual(supplied.cleaned_data["occurrence_key"], "external-proposal")
        fresh = CostHandoffForm(
            {"allocation": str(allocation.pk)}, organization=self.organization
        )
        fresh.fields["allocation"].clean = lambda value: allocation
        with patch(
            "apps.equipment.forms.EquipmentCostSourceEnvelope.objects.filter"
        ) as query:
            query.return_value.first.return_value = None
            self.assertTrue(fresh.is_valid(), fresh.errors)
        self.assertEqual(
            fresh.cleaned_data["occurrence_key"],
            f"equipment:project_cost:{allocation.pk}",
        )

    def document(self, title, *, linked=True, organization=None):
        organization = organization or self.organization
        document = Document.objects.create(
            organization=organization,
            document_number=f"DOC-{uuid4()}",
            title=title,
            created_by=self.actor,
        )
        versions = [
            DocumentVersion.objects.create(
                organization=organization,
                document=document,
                version_number=number,
                original_file_name=f"evidence-{number}.txt",
                file=f"test/evidence-{number}.txt",
                content_type="text/plain",
                file_size=1,
                sha256="a" * 64,
                uploaded_by=self.actor,
            )
            for number in (1, 2)
        ]
        document.current_version = versions[-1]
        document.save()
        if linked:
            ProjectDocumentLink.objects.create(
                organization=organization,
                document=document,
                project=self.project,
                created_by=self.actor,
            )
        return document, versions

    def test_dms_picker_uses_visibility_and_supports_safe_historical_versions(self):
        _, versions = self.document("Authorized evidence")
        self.document("Unlinked evidence", linked=False)
        self.document("Foreign evidence", organization=self.foreign, linked=False)
        with patch.object(
            DocumentVersion,
            "is_available",
            new_callable=PropertyMock,
            return_value=True,
        ):
            form = CloseoutEvidenceForm(
                organization=self.organization, actor=self.actor
            )
            self.assertEqual(
                set(form.fields["document_version_id"].queryset), set(versions)
            )
            for purpose, custom, expected in [
                ("closeout_support", "", "closeout_support"),
                ("custom", "legacy-purpose", "legacy-purpose"),
                ("", "legacy-purpose", "legacy-purpose"),
            ]:
                bound = CloseoutEvidenceForm(
                    {
                        "document_version_id": str(versions[0].pk),
                        "purpose": purpose,
                        "evidence_role": custom,
                    },
                    organization=self.organization,
                    actor=self.actor,
                )
                self.assertTrue(bound.is_valid(), bound.errors)
                self.assertEqual(bound.cleaned_data["evidence_role"], expected)
        with patch.object(
            DocumentVersion,
            "is_available",
            new_callable=PropertyMock,
            return_value=False,
        ):
            form = CloseoutEvidenceForm(
                organization=self.organization, actor=self.actor
            )
            self.assertFalse(form.fields["document_version_id"].queryset.exists())
        with self.assertRaises(PermissionDenied):
            CloseoutEvidenceForm(organization=self.organization, actor=self.outsider)
