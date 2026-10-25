from django.test import RequestFactory, TestCase

from apps.compliance.services import (
    create_inspection,
    create_template,
    publish_template_version,
    scoped_inspections,
)
from apps.compliance.views import record_detail, workbench
from apps.organizations.context_processors import business_permissions
from apps.organizations.models import BusinessPermission
from apps.safety import test_cep079_hse_scope as hse_fixture


class ComplianceReadScopeTests(TestCase):
    # Reuse the isolated organization/role/project fixture.
    def setUp(self):
        hse_fixture.HseWorkflowScopeTests.setUp(self)
        self.role.permissions.add(
            BusinessPermission.objects.get(code="compliance.view")
        )
        owner = self.org.created_by
        template = create_template(
            organization=self.org,
            actor=owner,
            profile="qa_qc",
            code="TEST",
            title="Test",
        )
        version = publish_template_version(
            organization=self.org,
            actor=owner,
            template_id=str(template.pk),
            checklist=[{"id": "test"}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[{"source": "test-only", "version": "1"}],
        )
        self.allowed = create_inspection(
            organization=self.org,
            actor=owner,
            project=self.project,
            site=self.site,
            profile="qa_qc",
            number="ALLOWED",
            template_version=version,
            title="Allowed",
            inspector=owner,
        )
        self.hidden = create_inspection(
            organization=self.org,
            actor=owner,
            project=self.denied,
            site=None,
            profile="qa_qc",
            number="HIDDEN",
            template_version=version,
            title="Hidden",
            inspector=owner,
        )

        other_owner = self.foreign.created_by
        other_template = create_template(
            organization=self.foreign,
            actor=other_owner,
            profile="qa_qc",
            code="FOREIGN",
            title="Foreign test",
        )
        other_version = publish_template_version(
            organization=self.foreign,
            actor=other_owner,
            template_id=str(other_template.pk),
            checklist=[{"id": "test"}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[{"source": "test-only", "version": "1"}],
        )
        self.foreign_record = create_inspection(
            organization=self.foreign,
            actor=other_owner,
            project=self.other,
            site=None,
            profile="qa_qc",
            number="FOREIGN",
            template_version=other_version,
            title="Foreign inspection",
            inspector=other_owner,
        )

    def request(self):
        request = RequestFactory().get("/compliance/")
        request.user, request.organization = self.user, self.org
        return request

    def test_scoped_workbench_and_detail_read(self):
        self.assertTrue(
            business_permissions(self.request())["compliance_workspace_available"]
        )
        self.assertEqual(
            list(scoped_inspections(organization=self.org, actor=self.user)),
            [self.allowed],
        )
        self.assertEqual(workbench(self.request()).status_code, 200)
        self.assertEqual(
            record_detail(self.request(), "inspection", self.allowed.pk).status_code,
            200,
        )

    def test_ungranted_foreign_missing_permission_and_inactive_denied(self):
        from uuid import uuid4

        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        with self.assertRaises(PermissionDenied):
            record_detail(self.request(), "inspection", self.hidden.pk)
        with self.assertRaises(Http404):
            record_detail(self.request(), "inspection", self.foreign_record.pk)
        with self.assertRaises(Http404):
            record_detail(self.request(), "inspection", uuid4())
        self.role.permissions.clear()
        self.assertFalse(
            business_permissions(self.request())["compliance_workspace_available"]
        )
        with self.assertRaises(PermissionDenied):
            workbench(self.request())
        self.role.permissions.add(
            BusinessPermission.objects.get(code="compliance.view")
        )
        self.membership.status = "suspended"
        self.membership.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            workbench(self.request())
