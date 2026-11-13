"""B09 document boundaries, exact retry semantics and safe HTTP feedback."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.contracts.contractual_services import add_contractual_evidence
from apps.contracts.forms import ContractualRecordForm
from apps.documents.forms import DocumentCreateForm, DocumentLinkForm
from apps.documents.models import Document
from apps.documents.test_contextual_association import ContextualAssociationTests, _Page
from apps.documents.test_evidence_integration import EvidenceIntegrationTests
from apps.documents.tests import DocumentServiceTests
from core.forms import parse_jalali_datetime
from core.product_surface import route_exposed


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class B09DocumentBoundaryTests(TestCase):
    setUp = DocumentServiceTests.setUp
    _pdf_upload = staticmethod(DocumentServiceTests._pdf_upload)
    _create_document = DocumentServiceTests._create_document
    login = ContextualAssociationTests.login
    contract = EvidenceIntegrationTests.contract
    contractual = EvidenceIntegrationTests.contractual

    def test_upload_expiry_uses_jalali_and_persists_aware_datetime(self):
        self.login()
        value = "1406/01/15 12:30"
        expected = timezone.make_aware(parse_jalali_datetime(value))
        form = DocumentCreateForm(organization=self.organization, user=self.owner)
        self.assertEqual(form.fields["access_expires_at"].widget.input_type, "text")
        for contextual in (False, True):
            with self.subTest(contextual=contextual):
                path = (
                    reverse(
                        "documents:contextual-upload", args=["project", self.project.pk]
                    )
                    if contextual
                    else reverse("documents:upload")
                )
                response = self.client.get(path)
                self.assertContains(response, 'data-jalali-date="datetime"')
                hidden = _Page(response.content.decode()).hidden if contextual else {}
                reference = f"B09-JALALI-{contextual}"
                result = self.client.post(
                    path,
                    {
                        **hidden,
                        "project": str(self.project.pk),
                        "document_type": "general",
                        "title": "سند دارای مهلت",
                        "reference": reference,
                        "confidentiality": "internal",
                        "access_expires_at": value,
                        "file": self._pdf_upload(),
                    },
                )
                self.assertEqual(result.status_code, 302)
                document = Document.objects.get(reference=reference)
                self.assertEqual(document.access_expires_at, expected)
                self.assertTrue(timezone.is_aware(document.access_expires_at))
                self.assertFalse(document.current_version.is_available)

    def test_mvp_document_forms_reject_hidden_treasury_target(self):
        for form_class in (DocumentCreateForm, DocumentLinkForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(organization=self.organization, user=self.owner)
                self.assertNotIn("treasury_movement", form.fields)
                with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
                    form = form_class(organization=self.organization, user=self.owner)
                    self.assertIn("treasury_movement", form.fields)

    def test_employee_routes_obey_mvp_exclusion_before_domain_access(self):
        self.login()
        document = self._create_document()
        cases = (
            ("employee-list", [], "get_employee_documents"),
            ("employee-detail", [document.pk], "get_employee_document"),
            (
                "employee-version-download",
                [document.pk, document.current_version_id],
                "record_employee_download",
            ),
        )
        for name, args, service in cases:
            with (
                self.subTest(route=name),
                patch(f"apps.documents.views.{service}") as domain,
            ):
                route = "documents:" + name
                self.assertFalse(route_exposed(route))
                path = reverse(route, args=args)
                for method in (self.client.get, self.client.post):
                    self.assertEqual(method(path).status_code, 403)
                    self.assertEqual(
                        method(path, HTTP_HX_REQUEST="true").status_code, 403
                    )
                domain.assert_not_called()
                with override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
                    self.assertTrue(route_exposed(route))
        self.assertTrue(route_exposed("documents:list"))

    def test_identical_contractual_evidence_retry_reuses_link_without_new_audit(self):
        record = self.contractual()
        document = self._create_document()
        kwargs = {
            "organization": self.organization,
            "actor": self.owner,
            "record": record,
            "label": "شاهد یکسان",
            "document_version": document.current_version,
        }
        first = add_contractual_evidence(**kwargs)
        before = AuditEvent.objects.count()
        second = add_contractual_evidence(**kwargs)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(record.evidence_links.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before)
        # A deliberately different business label remains a distinct reference.
        third = add_contractual_evidence(**{**kwargs, "label": "شاهد با عنوان دیگر"})
        self.assertNotEqual(first.pk, third.pk)

    def test_contractual_selector_excludes_sibling_project_and_denies_missing_actor(
        self,
    ):
        from apps.documents.test_related_documents import RelatedDocumentsTests
        from apps.projects.models import Project

        contract = self.contract()
        sibling = Project.objects.create(
            organization=self.organization, code="B09-SIBLING", name="پروژه دیگر"
        )
        reader = RelatedDocumentsTests.reader(
            self,
            ["contracts.view", "contractual_records.prepare"],
            project=sibling,
        )
        form = ContractualRecordForm(organization=self.organization, user=reader)
        self.assertNotIn(contract, form.fields["contract"].queryset)
        forged = ContractualRecordForm(
            {
                "contract": str(contract.pk),
                "kind": "claim",
                "record_number": "B09-FORGED",
                "title": "غیرمجاز",
                "description": "غیرمجاز",
            },
            organization=self.organization,
            user=reader,
        )
        self.assertFalse(forged.is_valid())
        self.assertIn("contract", forged.errors)
        self.assertFalse(
            ContractualRecordForm(organization=self.organization)
            .fields["contract"]
            .queryset.exists()
        )

    def test_stale_contractual_http_actions_show_feedback_without_side_effect(self):
        from apps.contracts.contractual_services import withdraw_contractual_record

        self.login()
        record = self.contractual()
        withdraw_contractual_record(
            organization=self.organization,
            actor=self.owner,
            record=record,
            reason="استرداد",
        )
        for action, data in (
            ("submit", {}),
            ("decide", {"outcome": "returned", "reason": "دلیل"}),
            ("revision", {"revision_action": "correction", "reason": "دلیل"}),
            ("withdraw", {"reason": "دلیل"}),
        ):
            with self.subTest(action=action):
                before = AuditEvent.objects.count()
                response = self.client.post(
                    reverse("contracts:contractual_" + action, args=[record.pk]), data
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(AuditEvent.objects.count(), before)
                feedback = self.client.get(response.url)
                self.assertContains(feedback, "وضعیت رکورد را دوباره بررسی کنید.")
                record.refresh_from_db()
                self.assertEqual(record.status, "withdrawn")
