"""Synthetic source and shared-Workflow proofs; no statutory activation."""

import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import OrganizationMembership
from apps.workflows.models import WorkflowInstance, WorkItem, WorkItemStatus
from apps.workflows.personal_workspaces import build_my_requests
from apps.workflows.runtime import claim_work_item
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)
from apps.workforce.person_services import create_person, create_work_relationship

from . import ess_services as ess
from . import test_p7_s23_s28_statutory_payroll as baseline
from .models import (
    PayrollInquiry,
    PayrollInquiryResponse,
    PayrollRun,
    PayrollRunEmployee,
    Payslip,
)
from .services import _payslip_payload

OWN = [
    P.PAYROLL_ESS_VIEW,
    P.PAYROLL_ESS_EXPORT,
    P.PAYROLL_INQUIRIES_VIEW,
    P.PAYROLL_INQUIRIES_REQUEST,
]
HANDLER = [
    P.PAYROLL_RESULTS_VIEW,
    P.PAYROLL_INQUIRIES_VIEW,
    P.PAYROLL_INQUIRIES_RESPOND,
    P.WORK_ITEMS_VIEW,
    P.WORK_ITEMS_CLAIM,
    P.WORK_ITEMS_ACT,
]


class ESSPayrollTests(baseline.StatutoryPayrollTests):
    def setUp(self):
        super().setUp()
        self.employee_user = self._member("ess-payroll", OWN)
        self.handler = self._member("inquiry-handler", HANDLER)
        self.unassigned = self._member("inquiry-unassigned", HANDLER)
        self.configurator = self._member(
            "inquiry-configurator",
            [
                P.PAYROLL_CONFIGURATION_MANAGE,
                P.WORKFLOWS_CREATE,
                P.WORKFLOWS_CHANGE_DRAFT,
                P.WORKFLOWS_PUBLISH,
            ],
        )
        person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="کارمند",
            last_name="نمونه",
            user=self.employee_user,
        )
        self.relationship = create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=person,
            employee_number=self.employee.employee_number,
            effective_start=timezone.localdate() - timedelta(days=90),
            legacy_employee=self.employee,
        )
        payload = _payslip_payload(self.run_employee)
        self.slip = Payslip.objects.create(
            organization=self.organization,
            run=self.run,
            run_employee=self.run_employee,
            number="ESS-SYNTHETIC-01",
            issued_at=timezone.now(),
            content_digest=Payslip.digest_payload(payload),
            presentation_snapshot=payload,
        )

    def _login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def _capture(self, name, response):
        directory = os.environ.get("BONIRA_CEP054_CAPTURE_DIR")
        if directory:
            Path(directory, name + ".html").write_bytes(response.content)

    def _category(self, decision_policy="any"):
        version = create_workflow_draft(
            actor=self.configurator,
            organization=self.organization,
            workflow_type_code="payroll.inquiry",
            code="synthetic-inquiry",
            name="پاسخ‌گویی حقوق آزمون",
            scope={},
        )
        config = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "response",
                    "step_type": "approval",
                    "required_permission": P.PAYROLL_INQUIRIES_RESPOND,
                    "configuration": {"decision_policy": decision_policy},
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {
                                "permission": P.PAYROLL_INQUIRIES_RESPOND
                            },
                        }
                    ],
                },
                {"key": "end", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "response",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {
                    "source": "response",
                    "target": "end",
                    "outcome": "answered",
                    "domain_command": "payroll.inquiry.respond",
                    "required_permission": P.PAYROLL_INQUIRIES_RESPOND,
                },
            ],
        }
        version = edit_workflow_draft(
            actor=self.configurator,
            organization=self.organization,
            version_id=version.pk,
            configuration=config,
        )
        version = publish_workflow_version(
            actor=self.configurator,
            organization=self.organization,
            version_id=version.pk,
        )
        return ess.configure_inquiry_category(
            actor=self.configurator,
            organization=self.organization,
            code="synthetic",
            name="پرسش آزمایشی",
            workflow_version=version,
            reason="Explicit synthetic fixture; no default category",
        )

    def _submit(self, category=None, **overrides):
        values = {
            "actor": self.employee_user,
            "organization": self.organization,
            "payslip_id": self.slip.pk,
            "category_id": (category or self._category()).pk,
            "subject": "پرسش درباره فیش قطعی",
            "description": "شرح پرسش نمونه",
            "idempotency_key": "question-1",
        }
        values.update(overrides)
        return ess.submit_inquiry(**values)

    def test_finalized_own_artifact_and_export_preserve_source(self):
        self._login(self.employee_user)
        history = self.client.get(reverse("payroll:ess_history"))
        self.assertContains(history, self.slip.number)
        self.assertContains(history, "1405/07/01")
        self._capture("history", history)
        response = self.client.get(reverse("payroll:ess_payslip", args=[self.slip.pk]))
        self.assertContains(response, "دریافت فیش قطعی")
        self.assertNotContains(
            response, reverse("payroll:payslip_export", args=[self.slip.pk])
        )
        self._capture("payslip", response)
        output = self.client.post(
            reverse("payroll:ess_payslip_export", args=[self.slip.pk])
        )
        self.assertEqual(output.status_code, 200)
        self.assertEqual(output.json(), self.slip.presentation_snapshot)
        self.assertEqual(
            self.client.get(
                reverse("payroll:ess_payslip_export", args=[self.slip.pk])
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(
                reverse("payroll:payslip_detail", args=[self.slip.pk])
            ).status_code,
            403,
        )
        self.run_employee.refresh_from_db()
        self.assertEqual(str(self.run_employee.net_amount), "1000.00")
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.employee_user,
                entity_id=str(self.slip.pk),
                action="payroll.payslip_exported",
            ).exists()
        )

    def test_own_identity_and_source_state_fail_closed(self):
        self._login(self.unassigned)
        denied = self.client.get(reverse("payroll:ess_payslip", args=[self.slip.pk]))
        missing = self.client.get(reverse("payroll:ess_payslip", args=[uuid4()]))
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.content, missing.content)
        self._capture("unauthorized", denied)
        self._login(self.employee_user)
        with patch(
            "apps.payroll.ess_views.services.own_payroll_history",
            side_effect=ValidationError("secret diagnostic"),
        ):
            error = self.client.get(reverse("payroll:ess_history"))
        self.assertEqual(error.status_code, 400)
        self.assertNotIn(b"secret diagnostic", error.content)
        self._capture("error", error)
        with patch(
            "apps.payroll.ess_views.services.own_payroll_history", return_value=()
        ):
            empty = self.client.get(reverse("payroll:ess_history"))
        self.assertContains(empty, "فیش قطعی مجازی برای نمایش موجود نیست.")
        self._capture("empty", empty)
        # A forged retained artifact for a draft run is never surfaced.
        PayrollRun.objects.filter(pk=self.run.pk).update(
            status="draft", finalized_at=None
        )
        self.assertEqual(
            ess.own_payroll_history(
                actor=self.employee_user, organization=self.organization
            ),
            (),
        )

    def test_submit_idempotency_and_my_requests_keep_workflow_authority(self):
        category = self._category()
        item = self._submit(category)
        self.assertEqual(self._submit(category).pk, item.pk)
        with self.assertRaises(ValidationError):
            self._submit(category, subject="different")
        instance = ess.inquiry_instance(item)
        self.assertEqual(instance.status, "active")
        self.assertEqual(WorkItem.objects.filter(instance=instance).count(), 1)
        self.assertEqual(WorkItem.objects.get(instance=instance).due_at, None)
        rows = build_my_requests(
            actor=self.employee_user, organization=self.organization
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, instance.status)
        self._login(self.employee_user)
        response = self.client.get(
            reverse("payroll:ess_inquiry_detail", args=[item.pk])
        )
        self.assertContains(response, item.subject)
        self.assertNotContains(response, "ثبت پاسخ و نتیجه")
        self._capture("inquiry", response)
        form = self.client.get(reverse("payroll:ess_inquiry_create"))
        self.assertEqual(form.status_code, 200)
        self._capture("inquiry-form", form)

    def test_missing_configuration_or_route_never_creates_orphan(self):
        with self.assertRaises(ValidationError):
            self._submit(category=type("Missing", (), {"pk": uuid4()})())
        self.assertEqual(PayrollInquiry.objects.count(), 0)
        category = self._category()
        # Explicitly configured route has no eligible responders after revocation.
        for user in (self.handler, self.unassigned):
            OrganizationMembership.objects.get(
                user=user, organization=self.organization
            ).role_definition.permissions.clear()
        with self.assertRaises(ValidationError):
            self._submit(category)
        self.assertEqual(PayrollInquiry.objects.count(), 0)
        self.assertEqual(
            WorkflowInstance.objects.filter(subject_type=ess.SUBJECT).count(), 0
        )

    def test_assigned_response_atomicity_privacy_and_no_financial_mutation(self):
        item = self._submit()
        work_item = WorkItem.objects.get(instance=ess.inquiry_instance(item))
        # Unassigned role alone will be tested by deactivating its candidacy.
        work_item.candidates.filter(membership__user=self.unassigned).update(
            is_active=False
        )
        with self.assertRaises(PermissionDenied):
            ess.get_inquiry(
                actor=self.unassigned,
                organization=self.organization,
                inquiry_id=item.pk,
            )
        claim_work_item(
            actor=self.handler,
            organization=self.organization,
            work_item_id=work_item.pk,
            idempotency_key="claim-1",
        )
        args = {
            "actor": self.handler,
            "organization": self.organization,
            "inquiry_id": item.pk,
            "work_item_id": work_item.pk,
            "outcome": "answered",
            "body": "پاسخ صریح برای کارمند",
            "idempotency_key": "response-1",
        }
        with self.assertRaises(ValidationError):
            ess.respond_inquiry(**(args | {"body": ""}))
        self.assertEqual(PayrollInquiryResponse.objects.count(), 0)
        work_item.refresh_from_db()
        self.assertEqual(work_item.status, WorkItemStatus.CLAIMED)
        with (
            patch(
                "apps.workflows.runtime.record_audit_event",
                side_effect=RuntimeError("audit-failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            ess.respond_inquiry(**args)
        self.assertEqual(PayrollInquiryResponse.objects.count(), 0)
        work_item.refresh_from_db()
        self.assertEqual(work_item.status, WorkItemStatus.CLAIMED)
        ess.respond_inquiry(**args)
        self.assertEqual(PayrollInquiryResponse.objects.count(), 1)
        with self.assertRaises(ValidationError):
            response = PayrollInquiryResponse.objects.get()
            response.body = "mutated"
            response.save()
        self.assertEqual(ess.inquiry_instance(item).status, "completed")
        self._login(self.employee_user)
        response = self.client.get(
            reverse("payroll:ess_inquiry_detail", args=[item.pk])
        )
        self.assertContains(response, args["body"])
        self._capture("response", response)
        self.slip.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(
            self.slip.content_digest,
            Payslip.digest_payload(self.slip.presentation_snapshot),
        )
        self.assertEqual(self.run.calculation_digest, "calculation-digest")
        self.assertEqual(
            PayrollRunEmployee.objects.get(pk=self.run_employee.pk).net_amount, 1000
        )

    def test_new_sensitive_permissions_have_no_builtin_default_grants(self):
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        codes = set(map(str, OWN + HANDLER)) & {
            "payroll_ess.view_own",
            "payroll_ess.export_own",
            "payroll_inquiries.view",
            "payroll_inquiries.request",
            "payroll_inquiries.respond",
        }
        for grants in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertFalse(codes & grants)

    def test_foreign_inquiry_and_payslip_urls_are_uniformly_denied(self):
        from apps.organizations.services import create_organization_with_owner

        foreign = create_organization_with_owner(
            owner=self.unassigned, name="Foreign tenant", slug="cep054-foreign"
        )
        with self.assertRaises(PermissionDenied):
            ess.own_payslip(
                actor=self.employee_user, organization=foreign, payslip_id=self.slip.pk
            )
        item = self._submit()
        self._login(self.denied)
        foreign_response = self.client.get(
            reverse("payroll:ess_inquiry_detail", args=[item.pk])
        )
        missing = self.client.get(reverse("payroll:ess_inquiry_detail", args=[uuid4()]))
        self.assertEqual(foreign_response.status_code, 403)
        self.assertEqual(foreign_response.content, missing.content)
        with self.assertRaises(PermissionDenied):
            self._submit(
                category=item.category, actor=self.unassigned, idempotency_key="forged"
            )

    def test_ui_handler_claim_response_uses_configured_outcome_only(self):
        item = self._submit()
        work_item = WorkItem.objects.get(instance=ess.inquiry_instance(item))
        self._login(self.handler)
        response = self.client.get(
            reverse("payroll:ess_inquiry_detail", args=[item.pk])
        )
        self.assertContains(response, "اخذ کار پاسخ‌گویی مجاز")
        self.assertEqual(
            self.client.post(
                reverse("payroll:ess_inquiry_claim", args=[item.pk, work_item.pk]),
                {"idempotency_key": "ui-claim"},
            ).status_code,
            302,
        )
        response = self.client.get(
            reverse("payroll:ess_inquiry_detail", args=[item.pk])
        )
        self.assertContains(response, 'value="answered"')
        self._capture("handler", response)
        invalid = self.client.post(
            reverse("payroll:ess_inquiry_detail", args=[item.pk]),
            {"outcome": "invented", "body": "پاسخ", "idempotency_key": "ui-response"},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(PayrollInquiryResponse.objects.count(), 0)
        result = self.client.post(
            reverse("payroll:ess_inquiry_detail", args=[item.pk]),
            {
                "outcome": "answered",
                "body": "پاسخ مجاز",
                "idempotency_key": "ui-response",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(PayrollInquiryResponse.objects.count(), 1)

    def test_replacement_lineage_is_source_linked_and_own_only(self):
        replacement = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="ESS-REPLACEMENT",
            kind="replacement",
            replaces=self.run,
            status="finalized",
            idempotency_key="replacement",
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        result = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=replacement,
            employee=self.employee,
            status="finalized",
            gross_amount=1200,
            net_amount=1200,
        )
        payload = _payslip_payload(result)
        slip = Payslip.objects.create(
            organization=self.organization,
            run=replacement,
            run_employee=result,
            number="ESS-REPLACED-02",
            issued_at=timezone.now(),
            content_digest=Payslip.digest_payload(payload),
            presentation_snapshot=payload,
        )
        self._login(self.employee_user)
        response = self.client.get(reverse("payroll:ess_payslip", args=[self.slip.pk]))
        self.assertContains(response, reverse("payroll:ess_payslip", args=[slip.pk]))
        self.assertContains(response, "زنجیره جایگزینی")
        self.assertEqual(
            len(
                ess.own_payroll_history(
                    actor=self.employee_user, organization=self.organization
                )
            ),
            2,
        )
        self._capture("lineage", response)

    def test_pinned_dms_evidence_obeys_own_assigned_privacy_on_all_paths(self):
        from apps.documents.models import (
            Document,
            DocumentProcessingAssessment,
            DocumentVersion,
        )
        from apps.documents.services import (
            add_document_link,
            get_document_version_for_download,
            get_organization_document,
            get_organization_documents,
        )
        from apps.organizations.models import BusinessPermission
        from apps.workforce.models import WorkRelationshipDocumentLink

        from .models import PayrollInquiryEvidenceLink

        for user in (self.employee_user, self.handler, self.unassigned):
            membership = OrganizationMembership.objects.get(
                organization=self.organization, user=user
            )
            membership.role_definition.permissions.add(
                *BusinessPermission.objects.filter(
                    code__in=[
                        P.DOCUMENTS_VIEW,
                        P.DOCUMENTS_DOWNLOAD,
                        P.DOCUMENTS_UPLOAD,
                        P.EMPLOYEES_VIEW,
                    ]
                )
            )
        document = Document.objects.create(
            organization=self.organization,
            document_number="CEP054-EVIDENCE",
            title="شاهد مصنوعی پرسش",
            created_by=self.owner,
        )
        version = DocumentVersion.objects.create(
            organization=self.organization,
            document=document,
            version_number=1,
            original_file_name="synthetic.pdf",
            file="synthetic/never-read.pdf",
            content_type="application/pdf",
            file_size=8,
            sha256="a" * 64,
            uploaded_by=self.owner,
        )
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=version,
            sequence=1,
            verdict="clean",
            input_sha256=version.sha256,
            adapter_code="synthetic-test",
            recorded_by=self.owner,
        )
        document.current_version = version
        document.save()
        WorkRelationshipDocumentLink.objects.create(
            organization=self.organization,
            document=document,
            work_relationship=self.relationship,
            created_by=self.owner,
        )
        item = self._submit(document_version_ids=(version.pk,))
        link = PayrollInquiryEvidenceLink.objects.get(payroll_inquiry=item)
        self.assertEqual(link.document_version_id, version.pk)
        task = WorkItem.objects.get(instance=ess.inquiry_instance(item))
        task.candidates.filter(membership__user=self.unassigned).update(is_active=False)
        self.assertFalse(
            get_organization_documents(
                user=self.unassigned, organization=self.organization
            )
            .filter(pk=document.pk)
            .exists()
        )
        with self.assertRaises(PermissionDenied):
            get_organization_document(
                user=self.unassigned,
                organization=self.organization,
                document_id=str(document.pk),
            )
        with self.assertRaises(PermissionDenied):
            get_document_version_for_download(
                document=document, version_id=str(version.pk), actor=self.unassigned
            )
        for user in (self.employee_user, self.handler):
            self.assertTrue(
                get_organization_documents(user=user, organization=self.organization)
                .filter(pk=document.pk)
                .exists()
            )
            self.assertEqual(
                get_document_version_for_download(
                    document=document, version_id=str(version.pk), actor=user
                ).pk,
                version.pk,
            )
        with self.assertRaises(PermissionDenied):
            add_document_link(document=document, actor=self.employee_user, target=item)
        with self.assertRaises(ValidationError):
            link.delete()
        with self.assertRaises(ValidationError):
            PayrollInquiryEvidenceLink.objects.filter(pk=link.pk).update(
                document_version_id=uuid4()
            )
        self._login(self.employee_user)
        self.assertContains(
            self.client.get(reverse("payroll:ess_inquiry_detail", args=[item.pk])),
            "شاهد مصنوعی پرسش",
        )

    def test_multi_actor_response_retained_before_shared_threshold(self):
        item = self._submit(category=self._category(decision_policy="all"))
        tasks = list(
            WorkItem.objects.filter(instance=ess.inquiry_instance(item)).order_by("pk")
        )
        for index, user in enumerate((self.handler, self.unassigned)):
            # All-policy creates one candidate-specific work item per actor.
            membership = OrganizationMembership.objects.get(
                user=user, organization=self.organization
            )
            task = next(
                t for t in tasks if t.candidates.filter(membership=membership).exists()
            )
            claim_work_item(
                actor=user,
                organization=self.organization,
                work_item_id=task.pk,
                idempotency_key=f"all-claim-{index}",
            )
            ess.respond_inquiry(
                actor=user,
                organization=self.organization,
                inquiry_id=item.pk,
                work_item_id=task.pk,
                outcome="answered",
                body=f"پاسخ صریح {index}",
                idempotency_key=f"all-response-{index}",
            )
            self.assertEqual(PayrollInquiryResponse.objects.count(), index + 1)
            self.assertEqual(
                ess.inquiry_instance(item).status,
                "active" if index == 0 else "completed",
            )
