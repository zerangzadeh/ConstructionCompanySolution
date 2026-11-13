"""PostgreSQL acceptance coverage for BON-DEF-0017."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.services import (
    add_document_version,
    create_document,
    record_document_processing_assessment,
)
from apps.organizations.access_services import assign_platform_role
from apps.organizations.models import (
    OrganizationRole,
    OrganizationStatus,
    PlatformRoleCode,
)
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.services import create_organization_with_owner
from apps.safety.models import SafetyIncident
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowType,
    WorkflowVersion,
)
from apps.workflows.runtime import WorkflowConflict, complete_work_item
from apps.workflows.services import publish_workflow_version
from tests.test_b02_remediation import B02Fixture

from .models import DailyReport
from .return_workflow import (
    adopt_submitted_report,
    publish_return_workflow,
    resubmit_correction,
    return_daily_report,
)
from .revision_services import save_correction, start_correction
from .services import (
    _approve_daily_report_domain,
    _submit_daily_report_domain,
    add_daily_activity,
    add_daily_report_equipment_entry,
    add_daily_report_labor_entry,
    add_daily_report_material_entry,
    add_delay_event,
    approve_daily_report,
    create_daily_report,
    get_organization_daily_reports,
    submit_daily_report,
)
from .submission_snapshots import ENTRIES, HEADER_FIELDS, verify_submission
from .workflow import (
    COMPATIBILITY_CONFIGURATION,
    COMPATIBILITY_DEFINITION_CODE,
    WORKFLOW_TYPE_CODE,
    _write_configuration,
)

AUTHOR_CODES = [
    "daily_reports.view",
    "daily_reports.create",
    "daily_reports.submit",
    "daily_reports.add_labor",
    "daily_reports.add_equipment",
    "daily_reports.add_material",
    "daily_reports.add_activity",
    "daily_reports.add_delay",
]
REVIEW_CODES = [
    "daily_reports.view",
    "daily_reports.approve",
    "work_items.view",
    "work_items.claim",
    "work_items.act",
]


class ReturnFixture(B02Fixture):
    def setUp(self):
        self.make_fixture()
        self.author, self.author_role, self.author_membership = self.member(
            "return-author",
            [*AUTHOR_CODES, "daily_reports.correct", *REVIEW_CODES[1:]],
            site=self.site,
        )
        self.reviewer, self.review_role, self.review_membership = self.member(
            "return-reviewer", REVIEW_CODES, site=self.site
        )
        self.other, _, _ = self.member("return-other", REVIEW_CODES, site=self.site)
        self.report = self.draft()

    def draft(self, day=7):
        return create_daily_report(
            organization=self.organization,
            actor=self.author,
            project=self.project,
            site=self.site,
            reporting_date=date(2026, 11, day),
            work_performed="شرح اولیه آزمایشی",
        )

    def args(self, report, actor):
        return {
            "organization": self.organization,
            "report_id": report.pk,
            "actor": actor,
        }

    def entries(self, report):
        kwargs = self.args(report, self.author)
        add_daily_report_labor_entry(
            **kwargs, team_name="تیم الف", worker_count=2, hours_worked=Decimal("7.00")
        )
        add_daily_report_equipment_entry(
            **kwargs, equipment_name="بیل", hours_used=Decimal("3.00")
        )
        add_daily_report_material_entry(
            **kwargs, material_name="سنگ", quantity=Decimal(3), unit="تن"
        )
        add_daily_activity(
            **kwargs, description="تسطیح", progress_percent=Decimal("20.00")
        )
        add_delay_event(**kwargs, occurred_on=report.reporting_date, cause="باران")

    def submit(self, report=None, actor=None):
        return submit_daily_report(
            **self.args(report or self.report, actor or self.author)
        )

    def returned(self, report=None, **params):
        return return_daily_report(
            **self.args(report or self.report, params.pop("actor", self.reviewer)),
            **({"reason": "اصلاح شرح و ردیف‌ها", "operation_key": uuid4()} | params),
        )

    def successor(self, report=None, **params):
        return start_correction(
            **self.args(report or self.report, params.pop("actor", self.author)),
            **({"operation_key": uuid4()} | params),
        )

    def resubmit(self, report, **params):
        return resubmit_correction(
            **self.args(report, params.pop("actor", self.author)),
            **(
                {"operation_key": uuid4(), "expected_version": report.edit_version}
                | params
            ),
        )

    def update_header(self, report, **params):
        return save_correction(
            **self.args(report, params.pop("actor", self.author)),
            **(
                {
                    "kind": "header",
                    "operation_key": uuid4(),
                    "expected_version": report.edit_version,
                    "values": {name: getattr(report, name) for name in HEADER_FIELDS}
                    | {"work_performed": "شرح اصلاح‌شده"},
                }
                | params
            ),
        )

    def event(self, report, action):
        return AuditEvent.objects.get(entity_id=str(report.pk), action=action)

    def work(self, report):
        return WorkflowInstance.objects.get(subject_id=report.pk).work_items.get()

    def legacy_version(self, configuration=None):
        workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE)
        definition = WorkflowDefinition.objects.create(
            organization=self.organization,
            workflow_type=workflow_type,
            code=COMPATIBILITY_DEFINITION_CODE,
            name="Legacy",
            scope={},
            created_by=self.owner,
            updated_by=self.owner,
        )
        draft = WorkflowVersion.objects.create(
            organization=self.organization,
            definition=definition,
            version_number=1,
            change_summary="W5.1 legacy compatibility",
        )
        _write_configuration(
            organization=self.organization,
            version=draft,
            configuration=configuration or COMPATIBILITY_CONFIGURATION,
        )
        return publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=draft.pk
        )


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class ReturnRevisionTests(ReturnFixture, TestCase):
    def test_correction_permission_is_absent_from_all_default_role_grants(self):
        self.assertTrue(
            all(
                "daily_reports.correct" not in grants
                for grants in DEFAULT_ROLE_PERMISSIONS.values()
            )
        )
        self.assertFalse(
            OrganizationRole.objects.filter(
                organization__isnull=True,
                permissions__code="daily_reports.correct",
            ).exists()
        )

    def test_complete_chain_exact_reads_and_all_entry_families(self):
        self.entries(self.report)
        first = self.submit()
        original = first.submission_snapshot
        item = self.work(first)
        key = uuid4()
        self.returned(first, operation_key=key)
        self.returned(first, operation_key=key)
        with self.assertRaises(WorkflowConflict):
            self.returned(first, operation_key=key, reason="changed")
        decision = self.event(first, AuditAction.DAILY_REPORT_RETURNED)
        self.assertEqual(decision.metadata["reason"], "اصلاح شرح و ردیف‌ها")
        self.assertEqual(decision.metadata["submission_hash"], first.submission_hash)
        key = uuid4()
        second = self.successor(first, operation_key=key)
        self.assertEqual(second.pk, self.successor(first, operation_key=key).pk)
        self.assertEqual(second.revision_number, 2)
        self.assertEqual(self.update_header(second), 1)
        with self.assertRaises(WorkflowConflict):
            self.update_header(second)
        second.refresh_from_db()
        for kind, spec in ENTRIES.items():
            row = getattr(second, spec.relation).get()
            self.assertNotEqual(row.pk, getattr(first, spec.relation).get().pk)
            values = {field: getattr(row, field) for field in spec.fields}
            field = {
                "labor": "team_name",
                "equipment": "equipment_name",
                "materials": "material_name",
                "activities": "description",
                "delays": "cause",
            }[kind]
            values[field] = "اصلاح ردیف"
            version = save_correction(
                **self.args(second, self.author),
                kind=kind,
                entry_id=row.pk,
                operation_key=uuid4(),
                expected_version=second.edit_version,
                values=values,
            )
            row.refresh_from_db()
            self.assertEqual(getattr(row, field), "اصلاح ردیف")
            second.edit_version = version
        labor = second.labor_entries.get()
        removal = uuid4()
        old_version = second.edit_version
        second.edit_version = save_correction(
            **self.args(second, self.author),
            kind="labor",
            entry_id=labor.pk,
            remove=True,
            operation_key=removal,
            expected_version=old_version,
            values={},
        )
        self.assertEqual(
            save_correction(
                **self.args(second, self.author),
                kind="labor",
                entry_id=labor.pk,
                remove=True,
                operation_key=removal,
                expected_version=old_version,
                values={},
            ),
            second.edit_version,
        )
        self.assertEqual(first.labor_entries.count(), 1)
        with self.assertRaises(PermissionDenied):
            add_daily_report_labor_entry(
                **self.args(second, self.author),
                team_name="X",
                worker_count=1,
                hours_worked=Decimal(1),
            )
        submit_key = uuid4()
        submitted = self.resubmit(second, operation_key=submit_key)
        self.resubmit(second, operation_key=submit_key)
        with self.assertRaises(WorkflowConflict):
            self.resubmit(second, operation_key=submit_key, expected_version=second.edit_version + 1)
        self.assertNotEqual(self.work(submitted).pk, item.pk)
        self.assertEqual(
            submitted.submission_snapshot["submitter_id"], str(self.author.pk)
        )
        self.assertFalse(
            self.work(submitted)
            .candidates.filter(membership=self.author_membership)
            .exists()
        )
        with self.assertRaises(WorkflowConflict):
            complete_work_item(
                organization=self.organization,
                actor=self.reviewer,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="stale-decision",
            )
        with (
            override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"),
            self.assertRaises(PermissionDenied),
        ):
            approve_daily_report(**self.args(submitted, self.author))
        approved = approve_daily_report(**self.args(submitted, self.reviewer))
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.approved_by, self.reviewer)
        verify_submission(approved)
        first.refresh_from_db()
        self.assertEqual(first.status, "returned")
        self.assertEqual(first.submission_snapshot, original)
        with self.assertRaises(WorkflowConflict):
            self.returned(approved)
        records = get_organization_daily_reports(
            user=self.author, organization=self.organization
        )
        self.assertEqual(
            list(
                records.filter(reporting_date=first.reporting_date).values_list(
                    "pk", flat=True
                )
            ),
            [approved.pk],
        )
        self.login(self.author)
        old_url = reverse("daily_reports:detail", args=[first.pk])
        self.assertContains(self.client.get(old_url), "اصلاح شرح و ردیف‌ها")
        self.assertContains(
            self.client.get(old_url + "?format=print"), "شرح اولیه آزمایشی"
        )
        self.assertNotContains(
            self.client.get(old_url + "?format=print"), "شرح اصلاح‌شده"
        )
        response = self.client.get(reverse("daily_reports:list") + "?format=xlsx")
        body = (
            b"".join(response.streaming_content)
            if response.streaming
            else response.content
        )
        with ZipFile(BytesIO(body)) as workbook:
            xml = "".join(
                workbook.read(name).decode()
                for name in workbook.namelist()
                if name.endswith(".xml")
            )
            self.assertIn("شرح اصلاح‌شده", xml)
            self.assertNotIn("شرح اولیه آزمایشی", xml)

    def test_default_denied_return_authority_and_workbench_post(self):
        no_correct, _, _ = self.member("no-correction", AUTHOR_CODES, site=self.site)
        blocked = create_daily_report(
            organization=self.organization,
            actor=no_correct,
            project=self.project,
            site=self.site,
            reporting_date=date(2026, 11, 8),
            work_performed="Blocked author",
        )
        first = self.submit(blocked, no_correct)
        for invalid_reason in ("  ", "ا" * 1001):
            with self.assertRaises(ValidationError):
                self.returned(first, reason=invalid_reason)
        self.returned(first)
        with self.assertRaises(PermissionDenied):
            self.successor(first, actor=no_correct)
        with self.assertRaises(PermissionDenied):
            self.successor(first)
        second = self.submit()
        sibling, _, _ = self.member("sibling-return", REVIEW_CODES, site=self.sibling)
        missing, _, _ = self.member(
            "missing-return", ["daily_reports.view"], site=self.site
        )
        for actor in (self.author, sibling, missing):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                self.returned(second, actor=actor)
        foreign = User.objects.create_user(username="return-foreign")
        foreign_org = create_organization_with_owner(
            owner=foreign, name="Foreign", slug="return-foreign"
        )
        with self.assertRaises(PermissionDenied):
            return_daily_report(
                organization=foreign_org,
                actor=foreign,
                report_id=second.pk,
                reason="Foreign",
                operation_key=uuid4(),
            )
        self.review_membership.status = "suspended"
        self.review_membership.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.returned(second)
        self.review_membership.status = "active"
        self.review_membership.save(update_fields=["status"])
        self.organization.__class__.objects.filter(pk=self.organization.pk).update(
            status=OrganizationStatus.SUSPENDED
        )
        with self.assertRaises(PermissionDenied):
            self.returned(second)
        self.organization.__class__.objects.filter(pk=self.organization.pk).update(
            status=OrganizationStatus.ACTIVE
        )
        item = self.work(second)
        self.login(self.reviewer)
        response = self.client.post(
            reverse("daily_reports:return", args=[second.pk]),
            {"reason": " ", "operation_key": uuid4()},
        )
        self.assertContains(response, "دلیل بازگشت", status_code=400)
        self.client.post(
            reverse("workflows:work_item_action", args=[item.pk]),
            {
                "outcome": "returned",
                "reason": "Generic POST",
                "idempotency_key": uuid4().hex,
            },
        )
        second.refresh_from_db()
        self.assertEqual(second.status, "submitted")
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_RETURNED, entity_id=str(second.pk)
            ).exists()
        )
        item.candidates.filter(membership=self.review_membership).update(
            is_active=False
        )
        with self.assertRaises(PermissionDenied):
            self.returned(second)
        with self.assertRaises(PermissionDenied):
            _approve_daily_report_domain(**self.args(second, self.other))

    def test_database_guards_and_original_uniqueness(self):
        self.entries(self.report)
        first = self.submit()
        second_root = self.draft(day=8)
        for operation in (
            lambda: DailyReport.objects.filter(pk=first.pk).update(
                work_performed="tamper"
            ),
            lambda: DailyReport.objects.filter(pk=first.pk).update(
                submission_snapshot={}
            ),
            lambda: DailyReport.objects.filter(pk=first.pk).delete(),
            lambda: DailyReport.objects.bulk_create(
                [
                    DailyReport(
                        organization=self.organization,
                        project=self.project,
                        site=self.site,
                        reporting_date=first.reporting_date,
                        work_performed="duplicate",
                    )
                ]
            ),
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()
        for spec in ENTRIES.values():
            row = getattr(first, spec.relation).get()
            queryset = spec.model.objects.filter(pk=row.pk)
            for operation in (
                lambda queryset=queryset: queryset.update(created_by=self.other),
                lambda queryset=queryset: queryset.update(report=second_root),
                queryset.delete,
                row.save,
            ):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    operation()
        with (
            self.assertRaises(IntegrityError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            DailyReport.objects.filter(pk=first.pk).update(status="returned")
            cursor.execute(
                "SET CONSTRAINTS bonira_daily_revision_decision_guard IMMEDIATE"
            )
        first.refresh_from_db()
        self.assertEqual(first.status, "submitted")

    def test_snapshot_pins_document_version_across_correction(self):
        doc = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type="general",
            title="شاهد نسخه اول",
            target=self.report,
            upload=SimpleUploadedFile(
                "one.pdf", b"%PDF-1.7\nOriginal", content_type="application/pdf"
            ),
        )
        with self.assertRaises(ValidationError):
            self.submit()
        self.report.refresh_from_db()
        self.assertEqual(
            (self.report.status, self.report.submission_hash), ("draft", "")
        )
        assigner = User.objects.create_superuser(username="return-assigner")
        approver = User.objects.create_superuser(username="return-approver")
        scanner = User.objects.create_user(username="return-scanner")
        assign_platform_role(
            actor=assigner,
            approver=approver,
            target=scanner,
            role=PlatformRoleCode.PLATFORM_OPERATIONS,
            reason="Synthetic evidence processing",
        )
        record_document_processing_assessment(
            version=doc.current_version,
            actor=scanner,
            verdict="clean",
            adapter_code="return-fixture",
        )
        incident = SafetyIncident.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            daily_report=self.report,
            incident_number="B03-R-SAFE",
            occurred_at=timezone.now(),
            incident_type="near_miss",
            severity="low",
            description="شرح ثبت‌شده شاهد ایمنی",
            created_by=self.owner,
            updated_by=self.owner,
        )
        first = self.submit()
        pinned = first.submission_snapshot["documents"][0]
        self.assertEqual(pinned["version_id"], str(doc.current_version_id))
        add_document_version(
            document=doc,
            actor=self.owner,
            upload=SimpleUploadedFile(
                "two.pdf", b"%PDF-1.7\nNew", content_type="application/pdf"
            ),
        )
        doc.refresh_from_db()
        self.assertNotEqual(str(doc.current_version_id), pinned["version_id"])
        self.returned(first)
        second = self.successor(first)
        second = self.resubmit(second)
        self.assertEqual(second.submission_snapshot["documents"], [pinned])
        latest_version_id = doc.current_version_id
        doc.refresh_from_db()
        self.assertEqual(doc.current_version_id, latest_version_id)
        self.assertEqual(doc.versions.count(), 2)
        self.assertEqual(
            second.submission_snapshot["references"],
            first.submission_snapshot["references"],
        )
        incident.refresh_from_db()
        self.assertEqual(incident.daily_report_id, first.pk)
        self.assertEqual(incident.status, "reported")
        self.login(self.author)
        self.assertNotContains(
            self.client.get(reverse("daily_reports:detail", args=[second.pk])),
            "شاهد نسخه اول",
        )

    def test_repeat_cycle_and_rollback_after_claim_or_seal(self):
        self.entries(self.report)
        first = self.submit()
        with (
            patch(
                "apps.daily_reports.return_workflow.write_receipt",
                side_effect=RuntimeError("audit failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.returned(first)
        first.refresh_from_db()
        self.assertEqual((first.status, self.work(first).status), ("submitted", "open"))
        self.returned(first)
        with (
            patch("apps.daily_reports.revision_services.write_receipt", side_effect=RuntimeError("clone audit failure")),
            self.assertRaises(RuntimeError),
        ):
            self.successor(first)
        self.assertFalse(DailyReport.objects.filter(previous_revision=first).exists())
        for spec in ENTRIES.values():
            self.assertEqual(spec.model.objects.filter(report=first).count(), 1)
        second = self.successor(first)
        with (
            patch(
                "apps.daily_reports.return_workflow.start_workflow",
                side_effect=RuntimeError("start failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.resubmit(second)
        second.refresh_from_db()
        self.assertEqual((second.status, second.submission_hash), ("draft", ""))
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=second.pk).exists())
        self.resubmit(second)
        self.returned(second)
        third = self.successor(second)
        self.assertEqual(
            (third.previous_revision_id, third.revision_number), (second.pk, 3)
        )

    def test_actual_submitter_cannot_return_and_no_reviewer_rolls_back_resubmission(
        self,
    ):
        manager, _, membership = self.member(
            "return-submitter",
            [*REVIEW_CODES, "daily_reports.submit"],
            site=self.site,
        )
        first = self.submit(actor=manager)
        self.assertEqual(
            first.submission_snapshot["submitter_membership_id"], str(membership.pk)
        )
        self.assertFalse(
            self.work(first).candidates.filter(membership=membership).exists()
        )
        with self.assertRaises(PermissionDenied):
            self.returned(first, actor=manager)
        self.returned(first)
        second = self.successor(first)
        self.organization.memberships.exclude(user=self.author).update(
            status="suspended"
        )
        with self.assertRaises(WorkflowConflict):
            self.resubmit(second)
        second.refresh_from_db()
        self.assertEqual((second.status, second.submission_hash), ("draft", ""))
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=second.pk).exists())

    def test_legacy_adoption_keeps_old_version_and_items_and_backfills_missing(self):
        legacy = self.legacy_version()
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            first = self.submit()
            old_item = self.work(first)
            unstarted = _submit_daily_report_domain(
                **self.args(self.draft(day=8), self.author)
            )
        with self.assertRaises(PermissionDenied):
            adopt_submitted_report(
                **self.args(first, self.reviewer), reason="test", operation_key=uuid4()
            )
        with self.assertRaises(WorkflowConflict):
            self.submit(self.draft(day=9))
        version = publish_return_workflow(
            organization=self.organization,
            actor=self.owner,
            reason="Enable governed Return",
        )
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, "retired")
        self.assertEqual(old_item.instance.version_id, legacy.pk)
        key = uuid4()
        first = adopt_submitted_report(
            **self.args(first, self.owner),
            reason="Evidence verified",
            operation_key=key,
        )
        adopt_submitted_report(
            **self.args(first, self.owner),
            reason="Evidence verified",
            operation_key=key,
        )
        self.assertEqual(first.submission_snapshot["provenance"], "legacy_capture")
        old_item.refresh_from_db()
        self.assertEqual(old_item.status, "cancelled")
        self.assertEqual(old_item.step_instance.step_definition.version_id, legacy.pk)
        self.assertEqual(old_item.instance.version_id, version.pk)
        self.returned(first)
        other = adopt_submitted_report(
            **self.args(unstarted, self.owner),
            reason="Backfill with evidence",
            operation_key=uuid4(),
        )
        self.assertEqual(self.work(other).instance.version_id, version.pk)
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            root = self.draft(day=10)
            self.submit(root)
            self.assertEqual(
                approve_daily_report(**self.args(root, self.author)).status, "approved"
            )

    def test_unprovable_legacy_submission_fails_closed(self):
        self.legacy_version()
        with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            first = self.submit()
        publish_return_workflow(
            organization=self.organization,
            actor=self.owner,
            reason="Enable governed Return",
        )
        DailyReport.objects.filter(pk=first.pk).update(updated_by=self.other)
        with self.assertRaises(WorkflowConflict):
            adopt_submitted_report(
                **self.args(first, self.owner),
                reason="Missing identity",
                operation_key=uuid4(),
            )
        first.refresh_from_db()
        self.assertEqual(first.submission_hash, "")
        self.assertEqual(self.work(first).status, "open")

    def test_custom_legacy_configuration_cannot_be_replaced_by_default(self):
        configuration = deepcopy(COMPATIBILITY_CONFIGURATION)
        configuration["steps"][1]["configuration"]["exclude_creator"] = True
        current = self.legacy_version(configuration)
        with self.assertRaises(WorkflowConflict):
            publish_return_workflow(
                organization=self.organization,
                actor=self.owner,
                reason="Custom policy must be preserved",
            )
        current.refresh_from_db()
        self.assertEqual(current.status, "published")
        self.assertEqual(current.definition.versions.count(), 1)

    def test_invalid_correction_values_and_snapshot_labels(self):
        self.entries(self.report)
        first = self.submit()
        self.returned(first)
        second = self.successor(first)
        for kind, spec in ENTRIES.items():
            entry = getattr(second, spec.relation).get()
            values = {name: getattr(entry, name) for name in spec.fields}
            field, bad = {
                "labor": ("worker_count", 0),
                "equipment": ("hours_used", Decimal(-1)),
                "materials": ("quantity", Decimal(-1)),
                "activities": ("progress_percent", Decimal(101)),
                "delays": ("duration_hours", Decimal(-1)),
            }[kind]
            values[field] = bad
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                save_correction(
                    **self.args(second, self.author),
                    kind=kind,
                    entry_id=entry.pk,
                    operation_key=uuid4(),
                    expected_version=0,
                    values=values,
                )
        second.refresh_from_db()
        self.assertEqual(second.edit_version, 0)
        original_label = first.project_label
        self.project.name = "نام جدید مرجع پروژه"
        self.project.save(update_fields=["name"])
        first.refresh_from_db()
        self.assertEqual(first.project_label, original_label)
        self.login(self.reviewer)
        response = self.client.get(reverse("daily_reports:detail", args=[first.pk]))
        self.assertContains(response, original_label)
        self.assertContains(response, "دلیل بازگشت")

    def test_correction_add_remove_all_families_and_http_validation(self):
        self.entries(self.report)
        first = self.submit()
        self.returned(first)
        second = self.successor(first)
        self.login(self.author)
        edit_url = reverse("daily_reports:correction", args=[second.pk])
        header = {name: getattr(second, name) for name in HEADER_FIELDS}
        invalid = self.client.post(
            edit_url,
            header
            | {
                "operation_key": uuid4(),
                "expected_version": 0,
                "work_performed": "",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        second.refresh_from_db()
        self.assertEqual(second.edit_version, 0)
        for kind, spec in ENTRIES.items():
            entry = getattr(second, spec.relation).get()
            values = {name: getattr(entry, name) for name in spec.fields}
            second.edit_version = save_correction(
                **self.args(second, self.author),
                kind=kind,
                entry_id=entry.pk,
                remove=True,
                values={},
                expected_version=second.edit_version,
                operation_key=uuid4(),
            )
            self.assertEqual(getattr(second, spec.relation).count(), 0)
            self.assertEqual(getattr(first, spec.relation).count(), 1)
            key = uuid4()
            expected = second.edit_version
            second.edit_version = save_correction(
                **self.args(second, self.author),
                kind=kind,
                values=values,
                expected_version=expected,
                operation_key=key,
            )
            self.assertEqual(
                save_correction(
                    **self.args(second, self.author),
                    kind=kind,
                    values=values,
                    expected_version=expected,
                    operation_key=key,
                ),
                second.edit_version,
            )
            self.assertEqual(getattr(second, spec.relation).count(), 1)
        self.login(self.other)
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(
            self.client.post(
                edit_url,
                header
                | {
                    "operation_key": uuid4(),
                    "expected_version": second.edit_version,
                },
            ).status_code,
            403,
        )
        second = self.resubmit(second)
        self.assertEqual(second.status, "submitted")


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class ReturnConcurrencyTests(ReturnFixture, TransactionTestCase):
    available_apps = [config.name for config in apps.get_app_configs()]  # noqa: RUF012

    def race(self, left, right):
        barrier = Barrier(2)

        def worker(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return operation()
            except (
                PermissionDenied,
                ValidationError,
                WorkflowConflict,
                ValueError,
            ) as exc:
                return type(exc).__name__
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, operation) for operation in (left, right)]
            return [future.result(timeout=45) for future in futures]

    def test_single_commit_under_concurrent_decision_creation_edit_and_submit(self):
        first = self.submit()
        outcomes = self.race(
            lambda: self.returned(first).status,
            lambda: approve_daily_report(**self.args(first, self.other)).status,
        )
        self.assertEqual(
            sum(outcome in ("approved", "returned") for outcome in outcomes), 1
        )
        first.refresh_from_db()
        self.assertEqual(self.work(first).completion_outcome, first.status)
        if first.status == "approved":
            first = self.submit(self.draft(day=8))
            self.returned(first)
        create_key = uuid4()
        outcomes = self.race(
            lambda: self.successor(first, operation_key=create_key).pk,
            lambda: self.successor(first, operation_key=create_key).pk,
        )
        self.assertEqual(outcomes[0], outcomes[1])
        second = DailyReport.objects.get(previous_revision=first)
        self.assertCountEqual(
            self.race(
                lambda: self.update_header(second), lambda: self.update_header(second)
            ),
            [1, "WorkflowConflict"],
        )
        second.refresh_from_db()
        key = uuid4()
        self.assertEqual(
            self.race(
                lambda: self.resubmit(second, operation_key=key).status,
                lambda: self.resubmit(second, operation_key=key).status,
            ),
            ["submitted", "submitted"],
        )
        self.assertEqual(
            WorkflowInstance.objects.filter(subject_id=second.pk).count(), 1
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                entity_id=str(second.pk), action=AuditAction.DAILY_REPORT_SUBMITTED
            ).count(),
            1,
        )
