from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.documents.models import DocumentType
from apps.documents.services import create_document
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermission, BusinessPermissionCode
from apps.organizations.services import create_organization_with_owner
from apps.workforce.models import Employee, EmployeeQualificationDocumentLink
from apps.workforce.services import (
    create_competency,
    create_skill,
    record_employee_qualification,
    record_employee_skill,
    record_labor_rate_version,
    record_performance_evaluation,
    revoke_employee_qualification,
)


class P7WorkforceFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p7-workforce-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="P7 Workforce", slug="p7-workforce"
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="P7-001",
            first_name="Workforce",
            last_name="Employee",
        )
        self.other_owner = User.objects.create_user(username="p7-other-owner")
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="P7 Other", slug="p7-other"
        )

    def test_skill_proficiency_history_is_tenant_scoped_immutable_and_non_overlapping(self) -> None:
        skill = create_skill(
            organization=self.organization,
            actor=self.owner,
            code="WELD",
            name="Welding",
        )
        competency = create_competency(
            organization=self.organization,
            actor=self.owner,
            code="WELD-Q",
            name="Welding competency",
        )
        record = record_employee_skill(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            skill=skill,
            competency=competency,
            proficiency_level=3,
            effective_from=date(2026, 1, 1),
        )
        with self.assertRaises(ValueError):
            record_employee_skill(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                skill=skill,
                competency=None,
                proficiency_level=4,
                effective_from=date(2026, 2, 1),
            )
        record.notes = "mutated"
        with self.assertRaises(ValidationError):
            record.save()
        other_skill = create_skill(
            organization=self.other_organization,
            actor=self.other_owner,
            code="OTHER",
            name="Other skill",
        )
        with self.assertRaises(PermissionDenied):
            record_employee_skill(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                skill=other_skill,
                competency=None,
                proficiency_level=2,
                effective_from=date(2027, 1, 1),
            )

    def test_qualification_revocation_and_typed_dms_evidence_preserve_history(self) -> None:
        qualification = record_employee_qualification(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            kind="certificate",
            title="Safety certificate",
            issued_on=date(2026, 1, 1),
            valid_until=date(2027, 1, 1),
        )
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.OTHER,
            title="Safety evidence",
            upload=SimpleUploadedFile("evidence.pdf", b"%PDF-1.4\nP7", content_type="application/pdf"),
            target=qualification,
        )
        self.assertTrue(
            EmployeeQualificationDocumentLink.objects.filter(
                organization=self.organization,
                document=document,
                document_version=document.current_version,
                qualification=qualification,
            ).exists()
        )
        event = revoke_employee_qualification(
            organization=self.organization,
            actor=self.owner,
            qualification=qualification,
            occurred_on=date(2026, 7, 1),
            reason="Issuer withdrawal",
        )
        self.assertEqual(event.kind, "revoked")
        self.assertFalse(qualification.is_valid_on(date(2026, 7, 2)))
        with self.assertRaises(ValueError):
            revoke_employee_qualification(
                organization=self.organization,
                actor=self.owner,
                qualification=qualification,
                occurred_on=date(2026, 7, 2),
                reason="duplicate",
            )

    def test_sensitive_performance_and_labor_rate_access_is_default_denied(self) -> None:
        self.assertFalse(
            has_business_permission(
                user=self.owner,
                organization=self.organization,
                permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW,
            )
        )
        with self.assertRaises(PermissionDenied):
            record_performance_evaluation(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
                criteria_snapshot={"safety": "met"},
                result_summary="Suitable",
            )
        membership = self.organization.memberships.get(user=self.owner)
        role = membership.role_assignments.get(revoked_at__isnull=True).role
        role.permissions.add(
            BusinessPermission.objects.get(code=BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE),
            BusinessPermission.objects.get(code=BusinessPermissionCode.WORKFORCE_LABOR_RATES_MANAGE),
        )
        evaluation = record_performance_evaluation(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            criteria_snapshot={"safety": "met"},
            result_summary="Suitable",
        )
        version = record_labor_rate_version(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            component_name="Base labor",
            unit_label="hour",
            currency_code="IRR",
            rate_amount=Decimal("100000.00"),
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(evaluation.employee_id, self.employee.pk)
        self.assertEqual(version.rate_amount, Decimal("100000.00"))
