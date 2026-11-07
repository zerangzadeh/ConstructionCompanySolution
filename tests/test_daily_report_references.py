"""Report references preserve source history, access boundaries and DMS rules."""

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from test_warehouse_reference_list import WarehouseListFixture

from apps.audit.models import AuditAction, AuditEvent
from apps.billing import test_mvp03_browser as browser_fixture
from apps.daily_reports.models import DailyReport, DailyReportRecordReference
from apps.daily_reports.reference_forms import DailyReportCreateForm
from apps.daily_reports.references import (
    create_report_with_references,
    report_reference_rows,
)
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import BusinessPermission, OrganizationSettings
from apps.projects.models import ProjectPhase, ProjectSite
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident
from apps.safety.record_review import decide_safety_record, submit_safety_record
from apps.safety.services import (
    assign_safety_incident,
    close_safety_incident,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from core.forms import format_jalali


class DailyReferenceFixture(WarehouseListFixture):
    def setup_daily(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        # Live-server isolation can restore the retained pre-extension seed.
        synchronize_authorization_catalog(using="default")
        self.make_fixture()
        temporary = TemporaryDirectory(prefix="bonira-daily-references-")
        self.addCleanup(temporary.cleanup)
        storage = override_settings(DOCUMENT_PROTECTED_ROOT=temporary.name)
        storage.enable()
        self.addCleanup(storage.disable)
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"timezone": "Asia/Tehran"}
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="DR-REF",
            name="کارگاه گزارش آزمون",
        )
        self.other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="DR-OTHER",
            name="کارگاه دیگر",
        )
        self.phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="DR-PHASE",
            name="فاز دیگر",
        )
        self.incident = self.safety(
            self.organization, self.project, self.site, "DR-SAFE"
        )
        self.issue = self.quality(
            self.organization, self.project, self.site, "DR-QUALITY"
        )
        self.document = create_document(
            organization=self.organization,
            actor=self.owner,
            target=self.project,
            document_type="general",
            title="سند موجود گزارش",
            upload=self.pdf(),
        )
        self.login(self.owner)

    @staticmethod
    def pdf():
        return SimpleUploadedFile(
            "daily-evidence.pdf",
            b"%PDF-1.7\nSynthetic daily report evidence\n%%EOF",
            content_type="application/pdf",
        )

    def safety(self, organization, project, site, number, phase=None):
        return SafetyIncident.objects.create(
            organization=organization,
            project=project,
            site=site,
            phase=phase,
            incident_number=number,
            occurred_at=timezone.now(),
            incident_type="near_miss",
            severity="low",
            description="مشاهده ایمنی ثبت‌شده",
            created_by=self.owner,
            updated_by=self.owner,
        )

    def quality(self, organization, project, site, number, phase=None):
        return QualityIssue.objects.create(
            organization=organization,
            project=project,
            site=site,
            phase=phase,
            issue_number=number,
            identified_at=timezone.now(),
            issue_type="defect",
            severity="minor",
            description="مسئله کیفیت ثبت‌شده",
            created_by=self.owner,
            updated_by=self.owner,
        )

    def report_values(self, day=5):
        return {
            "project": self.project,
            "site": self.site,
            "phase": None,
            "reporting_date": date(2026, 11, day),
            "work_performed": "فعالیت روزانه آزمون",
            "safety_notes": "یادداشت ایمنی",
            "quality_notes": "یادداشت کیفیت",
        }

    def post_values(self, day=5):
        return {
            "project": str(self.project.pk),
            "site": str(self.site.pk),
            "phase": "",
            "reporting_date": format_jalali(date(2026, 11, day)),
            "work_performed": "فعالیت روزانه آزمون",
            "labor_count": "2",
            "safety_notes": "یادداشت ایمنی",
            "quality_notes": "یادداشت کیفیت",
            "linked_safety_incidents": [str(self.incident.pk)],
            "linked_quality_issues": [str(self.issue.pk)],
            "linked_documents": [str(self.document.pk)],
        }


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class DailyReportReferenceTests(DailyReferenceFixture, TestCase):
    def setUp(self):
        self.setup_daily()

    def test_atomic_creation_reuses_documents_and_preserves_sources(self):
        before_safety = (
            SafetyIncident.objects.filter(pk=self.incident.pk).values().get()
        )
        before_quality = QualityIssue.objects.filter(pk=self.issue.pk).values().get()
        report = create_report_with_references(
            actor=self.owner,
            organization=self.organization,
            report_values=self.report_values(),
            safety_ids=[self.incident.pk],
            quality_ids=[self.issue.pk],
            document_ids=[self.document.pk],
            upload_values={
                "upload": self.pdf(),
                "title": "سند جدید گزارش",
                "document_type": "report",
            },
        )
        self.assertEqual(report.record_references.count(), 2)
        self.assertEqual(report.typed_document_links.count(), 2)
        self.assertEqual(report.safety_notes, "یادداشت ایمنی")
        self.assertEqual(report.quality_notes, "یادداشت کیفیت")
        self.assertEqual(
            SafetyIncident.objects.filter(pk=self.incident.pk).values().get(),
            before_safety,
        )
        self.assertEqual(
            QualityIssue.objects.filter(pk=self.issue.pk).values().get(), before_quality
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_RECORD_REFERENCED,
                entity_id=str(report.pk),
            ).count(),
            2,
        )
        response = self.client.get(reverse("daily_reports:detail", args=[report.pk]))
        self.assertContains(response, "DR-SAFE")
        self.assertContains(response, "DR-QUALITY")
        self.assertContains(response, "سند موجود گزارش")
        self.assertContains(response, "سند جدید گزارش")

    def test_closed_approved_source_can_be_referenced_by_multiple_reports(self):
        from apps.safety import workflow
        from apps.workflows.models import WorkflowTemplate, WorkflowType

        WorkflowTemplate.objects.get_or_create(
            workflow_type=WorkflowType.objects.get(code=workflow.WORKFLOW_TYPE_CODE),
            code=workflow.TEMPLATE_CODE,
            defaults={
                "name": workflow.TEMPLATE_CODE,
                "configuration": workflow.COMPATIBILITY_CONFIGURATION,
            },
        )
        submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            reason="آماده بررسی",
        )
        decide_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            outcome="approved",
            reason="بررسی مستقل رکورد",
        )
        review_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            due_date=timezone.localdate() + timedelta(days=7),
            responsible_user=self.owner,
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            corrective_action="ایمن‌سازی محل",
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            resolution_summary="رفع شد",
        )
        close_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            closure_summary="بسته شد",
        )
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, "closed")
        before = SafetyIncident.objects.filter(pk=self.incident.pk).values().get()
        for day in (5, 6):
            create_report_with_references(
                actor=self.owner,
                organization=self.organization,
                report_values=self.report_values(day),
                safety_ids=[self.incident.pk],
            )
        self.assertEqual(self.incident.daily_report_references.count(), 2)
        self.assertEqual(
            SafetyIncident.objects.filter(pk=self.incident.pk).values().get(), before
        )

    def test_tenant_site_phase_and_forged_identifiers_fail_atomically(self):
        self.other_organization.memberships.create(
            user=self.owner, role="member", status="active"
        )
        foreign_site = ProjectSite.objects.create(
            organization=self.other_organization,
            project=self.foreign_project(),
            code="FOREIGN",
            name="کارگاه شرکت دیگر",
        )
        foreign = self.safety(
            self.other_organization,
            foreign_site.project,
            foreign_site,
            "FOREIGN-SAFETY",
        )
        other_site = self.safety(
            self.organization, self.project, self.other_site, "OTHER-SITE"
        )
        other_phase = self.safety(
            self.organization, self.project, self.site, "OTHER-PHASE", self.phase
        )
        for identifier in (foreign.pk, other_site.pk, other_phase.pk, "forged"):
            with (
                self.subTest(identifier=identifier),
                self.assertRaises(PermissionDenied),
            ):
                create_report_with_references(
                    actor=self.owner,
                    organization=self.organization,
                    report_values=self.report_values(),
                    safety_ids=[identifier],
                )
            self.assertFalse(DailyReport.objects.exists())
            self.assertFalse(DailyReportRecordReference.objects.exists())
        response = self.client.post(
            reverse("daily_reports:create"),
            {**self.post_values(), "linked_safety_incidents": [str(other_site.pk)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(DailyReport.objects.exists())

    def foreign_project(self):
        from apps.projects.models import Project

        return Project.objects.create(
            organization=self.other_organization, code="FOREIGN-P", name="پروژه دیگر"
        )

    def test_lookup_permission_scope_pagination_and_form_retention(self):
        for index in range(22):
            self.safety(
                self.organization, self.project, self.site, f"LOOKUP-{index:02}"
            )
        path = reverse("daily_reports:reference_choices", args=["safety"])
        query = {"project": self.project.pk, "site": self.site.pk, "q": "LOOKUP"}
        response = self.client.get(path, query)
        self.assertEqual(len(response.json()["results"]), 20)
        self.assertTrue(response.json()["next"])
        self.assertEqual(
            len(self.client.get(path, {**query, "page": 2}).json()["results"]), 2
        )
        self.assertEqual(
            self.client.get(path, {**query, "site": self.other_site.pk}).json()[
                "results"
            ],
            [],
        )
        self.assertEqual(
            self.client.get(
                path, {**query, "project": self.hidden_project.pk}
            ).status_code,
            403,
        )
        response = self.client.post(
            reverse("daily_reports:create"),
            {**self.post_values(), "work_performed": ""},
        )
        form = response.context["form"]
        self.assertIn("work_performed", form.errors)
        for field, record in (
            ("linked_safety_incidents", self.incident),
            ("linked_quality_issues", self.issue),
            ("linked_documents", self.document),
        ):
            self.assertIn(str(record.pk), form[field].value())
        self.assertEqual(form["safety_notes"].value(), "یادداشت ایمنی")
        self.assertFalse(DailyReport.objects.exists())

    def test_explicit_permission_and_read_projection(self):
        report = create_report_with_references(
            actor=self.owner,
            organization=self.organization,
            report_values=self.report_values(),
            safety_ids=[self.incident.pk],
            quality_ids=[self.issue.pk],
        )
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "daily_reports.view",
                    "daily_reports.create",
                    "safety_incidents.view",
                ]
            )
        )
        membership = get_active_membership(
            user=self.reader, organization=self.organization
        )
        form = DailyReportCreateForm(
            organization=self.organization, membership=membership
        )
        self.assertNotIn("linked_safety_incidents", form.fields)
        self.login(self.reader)
        self.assertEqual(
            self.client.get(
                reverse("daily_reports:reference_choices", args=["safety"]),
                {"project": self.project.pk, "site": self.site.pk},
            ).status_code,
            403,
        )
        forged = self.client.post(
            reverse("daily_reports:create"),
            {
                **self.post_values(6),
                "linked_documents": [],
                "linked_quality_issues": [],
            },
        )
        self.assertTrue(forged.context["form"].errors)
        self.assertEqual(DailyReport.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            create_report_with_references(
                actor=self.reader,
                organization=self.organization,
                report_values=self.report_values(6),
                safety_ids=[self.incident.pk],
            )
        with self.assertRaises(PermissionDenied):
            create_report_with_references(
                actor=self.reader,
                organization=self.organization,
                report_values=self.report_values(6),
                document_ids=[self.document.pk],
            )
        self.assertEqual(DailyReport.objects.count(), 1)
        rows = report_reference_rows(
            actor=self.reader, organization=self.organization, report=report
        )
        self.assertEqual(list(rows["safety"]), [self.incident])
        self.assertNotIn("quality", rows)
        response = self.client.get(reverse("daily_reports:detail", args=[report.pk]))
        self.assertContains(response, "DR-SAFE")
        self.assertNotContains(response, "DR-QUALITY")

    def test_upload_validation_and_failure_roll_back_all_associations(self):
        data = self.post_values()
        data.update(
            {
                "upload-title": "سند آزمون",
                "upload-document_type": "report",
                "upload-file": SimpleUploadedFile(
                    "bad.pdf", b"not a pdf", content_type="application/pdf"
                ),
            }
        )
        response = self.client.post(reverse("daily_reports:create"), data)
        self.assertTrue(response.context["upload_form"].errors)
        self.assertFalse(DailyReport.objects.exists())
        before = Document.objects.count()
        from apps.daily_reports import references

        original = references.create_document

        def fail_after_storage(**kwargs):
            original(**kwargs)
            raise OSError("Synthetic storage interruption")

        with (
            patch.object(references, "create_document", side_effect=fail_after_storage),
            self.assertRaises(OSError),
        ):
            create_report_with_references(
                actor=self.owner,
                organization=self.organization,
                report_values=self.report_values(),
                safety_ids=[self.incident.pk],
                document_ids=[self.document.pk],
                upload_values={
                    "upload": self.pdf(),
                    "title": "سند جدید",
                    "document_type": "report",
                },
            )
        self.assertFalse(DailyReport.objects.exists())
        self.assertFalse(DailyReportRecordReference.objects.exists())
        self.assertEqual(Document.objects.count(), before)
        self.assertEqual(
            len(
                list(
                    Path(self.document.current_version.file.storage.location).rglob(
                        "*.pdf"
                    )
                )
            ),
            1,
        )

    def test_append_only_constraints_and_native_refresh(self):
        report = create_report_with_references(
            actor=self.owner,
            organization=self.organization,
            report_values=self.report_values(),
            safety_ids=[self.incident.pk],
        )
        reference = report.record_references.get()
        with self.assertRaises(ValidationError):
            reference.save()
        with self.assertRaises(ValidationError):
            reference.delete()
        with self.assertRaises(ValidationError):
            report.record_references.update(quality_issue=self.issue)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            DailyReportRecordReference.objects.bulk_create(
                [
                    DailyReportRecordReference(
                        organization=self.organization,
                        report=report,
                        created_by=self.owner,
                    )
                ]
            )
        data = {
            **self.post_values(6),
            "_refresh_choices": "1",
            "linked_safety_incidents": [],
            "linked_quality_issues": [],
            "linked_documents": [],
        }
        response = self.client.post(
            reverse("daily_reports:create") + "?native_choices=1", data
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DR-SAFE")
        self.assertEqual(DailyReport.objects.count(), 1)

    def test_revocation_and_suspended_tenant_fail_closed(self):
        self.organization.memberships.filter(user=self.owner).update(status="removed")
        with self.assertRaises(PermissionDenied):
            create_report_with_references(
                actor=self.owner,
                organization=self.organization,
                report_values=self.report_values(),
                safety_ids=[self.incident.pk],
            )
        self.assertFalse(DailyReport.objects.exists())
        self.organization.memberships.filter(user=self.owner).update(status="active")
        type(self.organization).objects.filter(pk=self.organization.pk).update(
            status="suspended"
        )
        with self.assertRaises(PermissionDenied):
            create_report_with_references(
                actor=self.owner,
                organization=self.organization,
                report_values=self.report_values(),
                safety_ids=[self.incident.pk],
            )
        self.assertFalse(DailyReport.objects.exists())


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class DailyReportReferenceBrowserTests(DailyReferenceFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/daily-report-association/browser")

    def test_real_chrome_reference_create_validation_and_navigation(self):
        self.setup_daily()
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
        }
        create = reverse("daily_reports:create")
        fields = self.post_values()
        response = self.client.get(create)
        self.assertIn(
            "linked_safety_incidents",
            response.context["form"].fields,
            {
                "fields": list(response.context["form"].fields),
                "codes": sorted(
                    set(response.context["business_permission_codes"])
                    & {
                        "daily_reports.link_records",
                        "safety_incidents.view",
                        "quality_issues.view",
                    }
                ),
            },
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"daily-create-{width}",
                    path=create,
                    width=width,
                    bottomScreenshot=True,
                )
                for width in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"daily-selection-validation-{width}",
                    path=create,
                    width=width,
                    preserveScrollScreenshot=True,
                    steps=[
                        {
                            "inspect": "document.querySelector('.erp-sectioned-form').noValidate = true",
                            "description": "exercise server validation after native validation remains enabled normally",
                        },
                        {
                            "fill": {
                                "project": fields["project"],
                                "site": fields["site"],
                            },
                            "waitMs": 400,
                            "inspect": "(()=>{const s=document.querySelector('select[name=linked_safety_incidents]');if(!s?.tomselect)throw new Error(JSON.stringify({ready:document.readyState,widget:!!s,guard:window.BoniraFieldChoices,tom:typeof window.TomSelect,scripts:[...document.scripts].map(s=>s.src)}));return true;})()",
                            "description": "shared multiple selector is initialized",
                        },
                        {
                            "searchChoice": {
                                "name": "linked_safety_incidents",
                                "query": "DR-SAFE",
                                "value": str(self.incident.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "linked_quality_issues",
                                "query": "DR-QUALITY",
                                "value": str(self.issue.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "linked_documents",
                                "query": "سند موجود",
                                "value": str(self.document.pk),
                            }
                        },
                        {
                            "fill": {
                                "reporting_date": fields["reporting_date"],
                                "labor_count": "2",
                                "safety_notes": "یادداشت ایمنی",
                                "quality_notes": "یادداشت کیفیت",
                            },
                            "submit": True,
                            "afterPath": create,
                        },
                        {
                            "inspect": "(()=>{document.querySelector('#form-references').scrollIntoView({block:'start'});return !!document.querySelector('.erp-field-error') && document.querySelector('select[name=linked_safety_incidents]').tomselect.items.length === 1 && document.querySelector('select[name=linked_quality_issues]').tomselect.items.length === 1 && document.querySelector('select[name=linked_documents]').tomselect.items.length === 1;})()",
                            "description": "validation retains all selected references",
                        },
                    ],
                )
                for width in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="daily-submit-references",
                    path=create,
                    steps=[
                        {
                            "fill": {
                                "project": fields["project"],
                                "site": fields["site"],
                            },
                            "inspect": "!!document.querySelector('select[name=linked_safety_incidents]').tomselect",
                            "description": "scope is selected",
                        },
                        {
                            "searchChoice": {
                                "name": "linked_safety_incidents",
                                "query": "DR-SAFE",
                                "value": str(self.incident.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "linked_quality_issues",
                                "query": "DR-QUALITY",
                                "value": str(self.issue.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "linked_documents",
                                "query": "سند موجود",
                                "value": str(self.document.pk),
                            }
                        },
                        {
                            "upload": {
                                "selector": "input[name=upload-file]",
                                "path": str(self.upload_evidence_path()),
                            }
                        },
                        {
                            "fill": {
                                **{
                                    name: value
                                    for name, value in fields.items()
                                    if name
                                    not in (
                                        "project",
                                        "site",
                                        "phase",
                                        "linked_safety_incidents",
                                        "linked_quality_issues",
                                        "linked_documents",
                                    )
                                },
                                "upload-title": "سند جدید گزارش مرورگر",
                                "upload-document_type": "report",
                            },
                            "submit": True,
                            "afterPrefix": "/daily-reports/",
                            "mustText": "DR-SAFE",
                        },
                        {
                            "inspect": "document.querySelectorAll('#report-record-references').length === 1 && document.body.textContent.includes('DR-QUALITY') && document.body.textContent.includes('سند موجود گزارش') && document.body.textContent.includes('سند جدید گزارش مرورگر')",
                            "description": "persisted references and document appear in Detail",
                        },
                    ],
                )
            ],
        )
        self.assertEqual(DailyReportRecordReference.objects.count(), 2)
        self.assertEqual(DailyReport.objects.get().typed_document_links.count(), 2)
        detail = reverse("daily_reports:detail", args=[DailyReport.objects.get().pk])
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"daily-linked-records-{width}",
                    path=detail,
                    width=width,
                    preserveScrollScreenshot=True,
                    steps=[
                        {
                            "inspect": "(()=>{document.querySelector('#report-record-references').scrollIntoView({block:'start'});return true;})()",
                            "description": "linked HSE records and DMS section",
                        }
                    ],
                )
                for width in (1440, 390)
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="daily-cancel-mobile",
                    path=create,
                    width=390,
                    steps=[
                        {
                            "clickSelector": "main .erp-form-footer a",
                            "afterPath": reverse("daily_reports:list"),
                        }
                    ],
                )
            ],
        )
        self.assertEqual(DailyReport.objects.count(), 1)
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=["daily_reports.create", "daily_reports.view"]
            )
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name="daily-restricted-create",
                    path=create,
                    width=390,
                    steps=[
                        {
                            "inspect": "!document.querySelector('[name=linked_safety_incidents]') && !document.querySelector('[name=linked_quality_issues]') && !document.querySelector('[name=linked_documents]') && !document.querySelector('[name=upload-file]')",
                            "description": "restricted actor can create a report without unauthorized association controls",
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"daily-references-section-{width}",
                    path=create,
                    width=width,
                    preserveScrollScreenshot=True,
                    steps=[
                        {
                            "inspect": "(()=>{document.querySelector('#form-references').scrollIntoView({block:'start'}); return document.querySelectorAll('main .erp-form-footer').length === 1;})()",
                            "description": "one normal-flow form footer and reference section",
                        }
                    ],
                )
                for width in (1440, 1024, 390)
            ],
        )

    def upload_evidence_path(self):
        path = self.browser_evidence_directory / "source-evidence.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.pdf().read())
        return path.resolve()
