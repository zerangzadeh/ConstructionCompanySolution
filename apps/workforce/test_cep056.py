"""Synthetic adapter contract tests; no official renderer or legal output."""

import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from apps.documents import test_cep011 as baseline
from apps.documents.employee_access import (
    get_employee_documents,
    get_employee_version_for_download,
)
from apps.documents.models import (
    Document,
)
from apps.documents.services import create_document
from apps.organizations.models import BusinessPermission, OrganizationMembership
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.models import WorkItem
from apps.workflows.personal_workspaces import build_my_requests, my_requests_available
from apps.workflows.runtime import claim_work_item, complete_work_item
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)
from apps.workforce.ess_dashboard import build_ess_dashboard

from . import certificate_services as service
from .models import (
    Employee,
    EmployeeQualification,
    EmployeeTrainingRecord,
    HRCertificateCancellation,
    HRCertificateGeneration,
    HRCertificateReview,
    HRCertificateType,
    TrainingRequirement,
)
from .own_evidence import build_own_evidence
from .person_services import end_work_relationship


class CertificateTests(TestCase):
    _relationship = baseline.EmployeeDocumentAccessTests._relationship
    _upload = staticmethod(baseline.EmployeeDocumentAccessTests._upload)
    _document = baseline.EmployeeDocumentAccessTests._document
    _allow = baseline.EmployeeDocumentAccessTests._allow
    _scan_clean = baseline.EmployeeDocumentAccessTests._scan_clean
    _client_as = baseline.EmployeeDocumentAccessTests._client_as

    def setUp(self):
        baseline.EmployeeDocumentAccessTests.setUp(self)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.WORKFORCE_QUALIFICATIONS_VIEW)
        )
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    P.ESS_EVIDENCE_VIEW,
                    P.HR_CERTIFICATES_VIEW,
                    P.HR_CERTIFICATES_REQUEST,
                ]
            )
        )
        self.generator = OrganizationMembership.objects.get(
            user=self.owner, organization=self.organization
        )
        self.generator.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    P.HR_CERTIFICATES_CONFIGURE,
                    P.HR_CERTIFICATES_VIEW,
                    P.HR_CERTIFICATES_GENERATE,
                    P.HR_CERTIFICATES_REVIEW,
                    P.HR_CERTIFICATES_CANCEL,
                    P.WORKFLOWS_CREATE,
                    P.WORKFLOWS_CHANGE_DRAFT,
                    P.WORKFLOWS_PUBLISH,
                    P.WORK_ITEMS_VIEW,
                    P.WORK_ITEMS_CLAIM,
                    P.WORK_ITEMS_ACT,
                ]
            )
        )
        self._allow(current=True, history=True, download=True)
        self.template = self._document()
        self._scan_clean(self.template.current_version)
        self.rendered = []

        def receipt(kind):
            return service.ActivationReceipt(
                str(kind.template_version_id),
                kind.template_version.sha256,
                "SYNTHETIC-NO-LEGAL-SIGNATURE",
                "SYNTHETIC-AUTHORITY-FIXTURE",
                "test-v1",
            )

        def render(**kwargs):
            self.rendered.append(kwargs["source_snapshot"])
            return SimpleUploadedFile(
                "synthetic.pdf",
                b"%PDF-1.7\nSYNTHETIC-NONOFFICIAL",
                content_type="application/pdf",
            )

        adapter = service.CertificateRenderer(
            resolve_activation=receipt,
            render=render,
            can_cancel_generated=lambda **kwargs: False,
        )
        override = patch.dict(service.RENDERERS, {"synthetic": adapter}, clear=True)
        override.start()
        self.addCleanup(override.stop)

    def _kind(self, *, enabled=True, review=None, source_map=None):
        return service.configure_type(
            actor=self.owner,
            organization=self.organization,
            code="synthetic",
            name="گواهی آزمایشی غیررسمی",
            source_map=source_map
            or {
                "first_name": "person.first_name",
                "employee_number": "relationship.employee_number",
            },
            template_version=self.template.current_version,
            category=self.category,
            generator=self.generator,
            renderer_key="synthetic",
            enabled=enabled,
            employee_visible=True,
            cancellation_before_output=True,
            reason="Synthetic contract test only",
            review_version=review,
        )

    def _submit(self, kind=None, key="request-1", replaces=None):
        return service.submit_request(
            actor=self.employee_user,
            organization=self.organization,
            type_id=(kind or self._kind()).pk,
            reason="درخواست نمونه غیررسمی",
            idempotency_key=key,
            replaces_id=replaces,
        )

    def _capture56(self, name, response):
        directory = os.environ.get("BONIRA_CEP056_CAPTURE_DIR")
        if directory:
            Path(directory, name + ".html").write_bytes(response.content)

    def _review_version(self):
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=service.SUBJECT,
            code="certificate-review",
            name="بررسی گواهی آزمون",
            scope={},
        )
        config = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "review",
                    "step_type": "approval",
                    "required_permission": P.HR_CERTIFICATES_REVIEW,
                    "configuration": {"decision_policy": "any"},
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {"permission": P.HR_CERTIFICATES_REVIEW},
                        }
                    ],
                },
                {"key": "accepted", "step_type": "end", "is_terminal": True},
                {"key": "rejected", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "review",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {
                    "source": "review",
                    "target": "accepted",
                    "outcome": "accepted",
                    "domain_command": service.SUBJECT + ".accept",
                    "required_permission": P.HR_CERTIFICATES_REVIEW,
                },
                {
                    "source": "review",
                    "target": "rejected",
                    "outcome": "rejected",
                    "domain_command": service.SUBJECT + ".reject",
                    "required_permission": P.HR_CERTIFICATES_REVIEW,
                },
            ],
        }
        version = edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=config,
        )
        return publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )

    def test_missing_renderer_or_activation_cannot_be_enabled_or_generate(self):
        kind = self._kind()
        item = self._submit(kind)
        service.RENDERERS.clear()
        self.assertEqual(
            service.available_types(
                actor=self.employee_user, organization=self.organization
            ),
            (),
        )
        with self.assertRaises(ValidationError):
            self._kind()
        with self.assertRaises(ValidationError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        self.assertEqual(HRCertificateGeneration.objects.count(), 0)
        self._client_as(self.employee_user)
        response = self.client.get(reverse("workforce:certificate_create"))
        self.assertContains(
            response, "نوع گواهی با قالب و سیاست امضای مجاز فعال در دسترس نیست."
        )
        self._capture56("unavailable", response)

    def test_no_review_pipeline_pins_source_template_and_safe_dms_download(self):
        kind = self._kind()
        item = self._submit(kind)
        self.assertEqual(self._submit(kind).pk, item.pk)
        self.assertEqual(HRCertificateGeneration.objects.count(), 0)
        with self.assertRaises(PermissionDenied):
            service.generate_certificate(
                actor=self.employee_user,
                organization=self.organization,
                request_id=item.pk,
            )
        output = service.generate_certificate(
            actor=self.owner, organization=self.organization, request_id=item.pk
        )
        self.assertEqual(
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            ).pk,
            output.pk,
        )
        self.assertEqual(output.template_version_id, self.template.current_version_id)
        self.assertEqual(output.source_digest, item.source_digest)
        self.assertEqual(self.rendered, [item.source_snapshot])
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(output.document_version.document_id),
                version_id=str(output.document_version_id),
            )
        self._scan_clean(output.document_version)
        self.assertEqual(
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(output.document_version.document_id),
                version_id=str(output.document_version_id),
            ).pk,
            output.document_version_id,
        )
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.other_user,
                organization=self.organization,
                document_id=str(output.document_version.document_id),
                version_id=str(output.document_version_id),
            )
        self._client_as(self.employee_user)
        response = self.client.get(
            reverse("workforce:certificate_detail", args=[item.pk])
        )
        self.assertContains(response, "دریافت نسخه مجاز سند")
        self._capture56("generated", response)
        form = self.client.get(reverse("workforce:certificate_create"))
        self.assertContains(form, "ثبت درخواست گواهی")
        self._capture56("form", form)

    def test_failed_database_or_audit_write_compensates_only_new_output_file(self):
        item = self._submit()
        root = Path(settings.DOCUMENT_PROTECTED_ROOT)
        before = {p for p in root.rglob("*") if p.is_file()}
        for target in (
            "apps.workforce.certificate_services.HRCertificateGeneration.objects.create",
            "apps.documents.services.record_audit_event",
        ):
            with (
                patch(target, side_effect=RuntimeError("synthetic-failure")),
                self.assertRaises(RuntimeError),
            ):
                service.generate_certificate(
                    actor=self.owner, organization=self.organization, request_id=item.pk
                )
            self.assertEqual({p for p in root.rglob("*") if p.is_file()}, before)
            self.assertEqual(Document.objects.count(), 1)
            self.assertEqual(HRCertificateGeneration.objects.count(), 0)
        self.assertTrue(Path(self.template.current_version.file.path).exists())
        with transaction.atomic(), self.assertRaises(RuntimeError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        self.assertEqual({p for p in root.rglob("*") if p.is_file()}, before)

    def test_corrupt_template_and_retired_type_fail_closed(self):
        kind = self._kind()
        item = self._submit(kind)
        path = Path(self.template.current_version.file.path)
        original = path.read_bytes()
        path.write_bytes(b"tampered")
        with self.assertRaises(ValidationError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        path.write_bytes(original)
        self._kind(enabled=False)
        self.assertEqual(
            service.available_types(
                actor=self.employee_user, organization=self.organization
            ),
            (),
        )
        with self.assertRaises(ValidationError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        self.assertEqual(HRCertificateGeneration.objects.count(), 0)

    def test_optional_review_requires_actual_claimed_work_item_and_no_private_note(
        self,
    ):
        kind = self._kind(review=self._review_version())
        item = self._submit(kind)
        with self.assertRaises(ValidationError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        task = WorkItem.objects.get(instance=service.instance_for(item))
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=task.pk,
            idempotency_key="claim-1",
        )
        with self.assertRaises(ValidationError):
            complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=task.pk,
                outcome="accepted",
                idempotency_key="decision-1",
            )
        complete_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=task.pk,
            outcome="accepted",
            idempotency_key="decision-1",
            command_context={"employee_visible_reason": "پذیرش بررسی غیررسمی"},
        )
        self.assertEqual(
            HRCertificateReview.objects.get(request=item).outcome, "accepted"
        )
        self.assertTrue(
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=item.pk
            )
        )

    def test_replacement_history_and_cancellation_never_overwrite_existing_artifact(
        self,
    ):
        kind = self._kind()
        item = self._submit(kind)
        output = service.generate_certificate(
            actor=self.owner, organization=self.organization, request_id=item.pk
        )
        replacement = self._submit(kind, key="request-2", replaces=item.pk)
        self.assertEqual(replacement.replaces_id, item.pk)
        service.generate_certificate(
            actor=self.owner, organization=self.organization, request_id=replacement.pk
        )
        output.refresh_from_db()
        self.assertTrue(Path(output.document_version.file.path).exists())
        pending = self._submit(kind, key="request-3")
        service.cancel_request(
            actor=self.employee_user,
            organization=self.organization,
            request_id=pending.pk,
            reason="لغو درخواست پیش از خروجی",
            idempotency_key="cancel-3",
        )
        self.assertTrue(
            HRCertificateCancellation.objects.filter(request=pending).exists()
        )
        with self.assertRaises(ValidationError):
            service.generate_certificate(
                actor=self.owner, organization=self.organization, request_id=pending.pk
            )
        with self.assertRaises(ValidationError):
            service.cancel_request(
                actor=self.owner,
                organization=self.organization,
                request_id=item.pk,
                reason="No signature cancellation policy",
                idempotency_key="cancel-issued",
            )
        self.assertEqual(HRCertificateGeneration.objects.count(), 2)

    def test_no_legacy_employee_required_for_certificate_and_my_requests(self):
        item = self._submit()
        self.assertIsNone(self.relationship.legacy_employee_id)
        self.assertTrue(
            my_requests_available(
                actor=self.employee_user, organization=self.organization
            )
        )
        rows = build_my_requests(
            actor=self.employee_user, organization=self.organization
        )
        self.assertEqual([r.source_id for r in rows], [item.pk])
        dashboard = build_ess_dashboard(
            user=self.employee_user, organization=self.organization
        )
        self.assertEqual([r.source_id for r in dashboard.requests], [item.pk])
        self._client_as(self.employee_user)
        response = self.client.get(
            reverse("workforce:certificate_detail", args=[item.pk])
        )
        self.assertContains(response, "داده‌های مقید به منبع درخواست")
        self._capture56("request", response)

    def test_evidence_is_own_source_read_only_without_broad_backoffice_grant(self):
        end_work_relationship(
            organization=self.organization,
            actor=self.owner,
            relationship=self.relationship,
            effective_end=self.today - timedelta(days=1),
        )
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="E-NEW",
            first_name="آزمون",
            last_name="خودم",
        )
        self.relationship = self._relationship(
            self.person, "E-NEW", start=self.today, legacy=employee
        )
        qualification = EmployeeQualification.objects.create(
            organization=self.organization,
            employee=employee,
            kind="certificate",
            title="صلاحیت منبع شخصی",
            issued_on=self.today,
            recorded_by=self.owner,
        )
        requirement = TrainingRequirement.objects.create(
            organization=self.organization,
            code="SYNTHETIC",
            name="آموزش منبع شخصی",
            created_by=self.owner,
        )
        EmployeeTrainingRecord.objects.create(
            organization=self.organization,
            employee=employee,
            requirement=requirement,
            occurred_on=self.today,
            outcome="completed",
            notes="CONFIDENTIAL-INTERNAL-NOTE",
            recorded_by=self.owner,
        )
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type="other",
            title="شاهد صلاحیت شخصی",
            upload=self._upload(),
            target=qualification,
            category=self.category,
        )
        self._scan_clean(document.current_version)
        evidence = build_own_evidence(
            actor=self.employee_user, organization=self.organization
        )
        self.assertEqual([q.pk for q in evidence.qualifications], [qualification.pk])
        self.assertIn(
            document.pk,
            {
                d.document.pk
                for d in get_employee_documents(
                    user=self.employee_user, organization=self.organization
                )
            },
        )
        self._client_as(self.employee_user)
        response = self.client.get(reverse("workforce:own_evidence"))
        self.assertContains(response, "صلاحیت منبع شخصی")
        self.assertContains(response, "آموزش منبع شخصی")
        self.assertNotContains(response, "CONFIDENTIAL-INTERNAL-NOTE")
        self._capture56("evidence", response)
        self.assertEqual(
            self.client.post(
                reverse("workforce:own_evidence"), {"title": "self-certified"}
            ).status_code,
            405,
        )
        self.assertEqual(EmployeeQualification.objects.count(), 1)

    def test_empty_error_uniform_denial_and_owner_admin_sensitive_defaults_denied(self):
        self._client_as(self.employee_user)
        empty = self.client.get(reverse("workforce:certificate_index"))
        self.assertContains(empty, "درخواست گواهی مجازی برای نمایش موجود نیست.")
        self._capture56("empty", empty)
        with patch(
            "apps.workforce.certificate_views.build_own_evidence",
            side_effect=ValidationError("private diagnostic"),
        ):
            error = self.client.get(reverse("workforce:own_evidence"))
        self.assertEqual(error.status_code, 400)
        self.assertNotIn(b"private diagnostic", error.content)
        self._capture56("error", error)
        item = self._submit()
        self._client_as(self.other_user)
        denied = self.client.get(
            reverse("workforce:certificate_detail", args=[item.pk])
        )
        missing = self.client.get(
            reverse("workforce:certificate_detail", args=[uuid4()])
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.content, missing.content)
        self._capture56("unauthorized", denied)
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        codes = {
            P.ESS_EVIDENCE_VIEW,
            P.HR_CERTIFICATES_VIEW,
            P.HR_CERTIFICATES_REQUEST,
            P.HR_CERTIFICATES_REVIEW,
            P.HR_CERTIFICATES_GENERATE,
            P.HR_CERTIFICATES_CONFIGURE,
            P.HR_CERTIFICATES_CANCEL,
        }
        for grants in (
            DEFAULT_ROLE_PERMISSIONS[role] for role in ("tenant_owner", "tenant_admin")
        ):
            self.assertFalse(codes & grants)

    def test_foreign_tenant_and_unassigned_member_cannot_read_or_generate(self):
        item = self._submit()
        with self.assertRaises(PermissionDenied):
            service.get_request(
                actor=self.other_user,
                organization=self.organization,
                request_id=item.pk,
            )
        with self.assertRaises(PermissionDenied):
            service.generate_certificate(
                actor=self.other_user,
                organization=self.organization,
                request_id=item.pk,
            )
        from apps.organizations.services import create_organization_with_owner

        foreign = create_organization_with_owner(
            owner=self.other_user, name="Foreign", slug="cep056-foreign"
        )
        with self.assertRaises(PermissionDenied):
            service.get_request(
                actor=self.employee_user, organization=foreign, request_id=item.pk
            )
        self.assertEqual(HRCertificateGeneration.objects.count(), 0)

    def test_closed_source_map_and_mismatched_activation_receipt_are_rejected(self):
        for field in (
            "payroll.net_amount",
            "person.national_id",
            "user.email",
            "__class__",
        ):
            with self.assertRaises(ValidationError):
                self._kind(source_map={"forbidden": field})
        from dataclasses import replace

        old = service.RENDERERS["synthetic"]
        invalid = replace(
            old,
            resolve_activation=lambda kind: service.ActivationReceipt(
                str(uuid4()),
                kind.template_version.sha256,
                "SYNTHETIC",
                "SYNTHETIC",
                "test",
            ),
        )
        with (
            patch.dict(service.RENDERERS, {"synthetic": invalid}),
            self.assertRaises(ValidationError),
        ):
            self._kind()
        self.assertEqual(HRCertificateType.objects.count(), 0)

    def test_pinned_source_dates_are_jalali_in_presentation_only(self):
        from core.jalali import format_jalali

        kind = self._kind(source_map={"starts": "relationship.effective_start"})
        item = self._submit(kind)
        self.assertEqual(
            item.source_snapshot["fields"]["starts"],
            self.relationship.effective_start.isoformat(),
        )
        self._client_as(self.employee_user)
        response = self.client.get(
            reverse("workforce:certificate_detail", args=[item.pk])
        )
        self.assertContains(response, format_jalali(self.relationship.effective_start))
        self.assertNotContains(response, self.relationship.effective_start.isoformat())

    def test_generic_dms_and_employee_paths_cannot_bypass_certificate_case_scope(self):
        from apps.documents.services import (
            get_document_version_for_download,
            get_organization_document,
            get_organization_documents,
        )

        item = self._submit()
        output = service.generate_certificate(
            actor=self.owner, organization=self.organization, request_id=item.pk
        )
        self._scan_clean(output.document_version)
        # A reader has broad Workforce + DMS access but no certificate case.
        self.role.permissions.add(BusinessPermission.objects.get(code=P.EMPLOYEES_VIEW))
        document = output.document_version.document
        self.assertFalse(
            get_organization_documents(
                user=self.other_user, organization=self.organization
            )
            .filter(pk=document.pk)
            .exists()
        )
        with self.assertRaises(PermissionDenied):
            get_organization_document(
                user=self.other_user,
                organization=self.organization,
                document_id=str(document.pk),
            )
        with self.assertRaises(PermissionDenied):
            get_document_version_for_download(
                document=document,
                version_id=str(output.document_version_id),
                actor=self.other_user,
            )
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.HR_CERTIFICATES_VIEW)
        )
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(output.document_version_id),
            )
        self.assertNotIn(
            document.pk,
            {
                access.document.pk
                for access in get_employee_documents(
                    user=self.employee_user, organization=self.organization
                )
            },
        )
