"""CEP-011 employee DMS policy, identity, source and endpoint checks."""

from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.employee_access import (
    get_employee_document,
    get_employee_documents,
    get_employee_version_for_download,
)
from apps.documents.link_registry import create_typed_link
from apps.documents.models import DocumentProcessingAssessment, DocumentType
from apps.documents.services import (
    add_document_link,
    add_document_version,
    create_document,
    create_document_category,
    get_organization_document,
    set_document_category_employee_policy,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.projects.services import create_project
from apps.workforce.models import Employee, EmployeeQualification, QualificationKind
from apps.workforce.person_services import create_person, create_work_relationship


class EmployeeDocumentAccessTests(TestCase):
    def setUp(self) -> None:
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_settings = override_settings(
            MEDIA_ROOT=media.name, DOCUMENT_PROTECTED_ROOT=media.name
        )
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.owner = User.objects.create_user(username="cep011-owner")
        self.employee_user = User.objects.create_user(username="cep011-employee")
        self.other_user = User.objects.create_user(username="cep011-other")
        self.organization = Organization.objects.create(
            name="CEP011 Company",
            slug="cep011-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationSettings.objects.create(organization=self.organization)
        owner_role = OrganizationRole.objects.create(
            code="cep011_setup", name="DMS and Workforce setup"
        )
        owner_role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.EMPLOYEES_CREATE,
                    BusinessPermissionCode.EMPLOYEES_CHANGE_STATUS,
                    BusinessPermissionCode.EMPLOYEES_VIEW,
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
                    BusinessPermissionCode.DOCUMENTS_UPLOAD,
                    BusinessPermissionCode.DOCUMENT_CATEGORIES_MANAGE,
                    BusinessPermissionCode.PROJECTS_CREATE,
                    BusinessPermissionCode.PROJECTS_VIEW,
                    BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
                ]
            )
        )
        owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            role_definition=owner_role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=owner_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-011 setup",
        )
        self.role = OrganizationRole.objects.create(
            code="cep011_reader", name="DMS reader"
        )
        self.role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
                    BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
                ]
            )
        )
        for user in (self.employee_user, self.other_user):
            membership = OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role_definition=self.role,
                status=MembershipStatus.ACTIVE,
            )
            MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="CEP-011 reader",
            )
        self.person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Test",
            last_name="Employee",
            user=self.employee_user,
        )
        self.other_person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="Other",
            last_name="Employee",
            user=self.other_user,
        )
        self.today = timezone.localdate()
        self.relationship = self._relationship(self.person, "E-011")
        self.other_relationship = self._relationship(self.other_person, "E-012")
        self.category = create_document_category(
            organization=self.organization,
            actor=self.owner,
            code="employment",
            name="Employment",
        )

    def _relationship(self, person, number, *, start=None, end=None, legacy=None):
        return create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=person,
            employee_number=number,
            effective_start=start or self.today - timedelta(days=30),
            effective_end=end,
            legacy_employee=legacy,
        )

    @staticmethod
    def _upload(name="evidence.pdf"):
        return SimpleUploadedFile(
            name, b"%PDF-1.7\nevidence", content_type="application/pdf"
        )

    def _document(self, relationship=None, *, category=None):
        return create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Employment evidence",
            upload=self._upload(),
            target=relationship or self.relationship,
            category=category or self.category,
        )

    def _allow(self, *, current=True, history=False, download=False):
        self.category = set_document_category_employee_policy(
            category=self.category,
            actor=self.owner,
            employee_current_visible=current,
            employee_history_visible=history,
            employee_download_allowed=download,
        )

    def _scan_clean(self, version):
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=version,
            sequence=1,
            verdict="clean",
            input_sha256=version.sha256,
            adapter_code="cep011-test",
            recorded_by=self.owner,
        )

    def _client_as(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def test_default_deny_and_category_policy_is_audited(self):
        document = self._document()
        self.assertEqual(
            get_employee_documents(
                user=self.employee_user, organization=self.organization
            ),
            [],
        )
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
            )
        self._allow(current=True)
        access = get_employee_document(
            user=self.employee_user,
            organization=self.organization,
            document_id=str(document.pk),
        )
        self.assertEqual([v.pk for v in access.versions], [document.current_version_id])
        self.assertIn(
            ("work_relationship", str(self.relationship.pk)), access.source_links
        )
        self.assertFalse(access.can_download)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_CATEGORY_POLICY_UPDATED,
                entity_id=str(self.category.pk),
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            set_document_category_employee_policy(
                category=self.category,
                actor=self.other_user,
                employee_current_visible=False,
                employee_history_visible=False,
                employee_download_allowed=False,
            )

    def test_version_visibility_and_download_are_separate_and_rechecked(self):
        document = self._document()
        first = document.current_version
        second = add_document_version(
            document=document, actor=self.owner, upload=self._upload("new.pdf")
        )
        document.refresh_from_db()
        self._scan_clean(first)
        self._scan_clean(second)
        self._allow(current=True, history=False, download=False)
        access = get_employee_document(
            user=self.employee_user,
            organization=self.organization,
            document_id=str(document.pk),
        )
        self.assertEqual([v.pk for v in access.versions], [second.pk])
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(second.pk),
            )
        self.role.permissions.remove(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.DOCUMENTS_DOWNLOAD
            )
        )
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(first.pk),
            )
        self.role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.DOCUMENTS_DOWNLOAD
            )
        )
        self._allow(current=False, history=True, download=True)
        access = get_employee_document(
            user=self.employee_user,
            organization=self.organization,
            document_id=str(document.pk),
        )
        self.assertEqual([v.pk for v in access.versions], [first.pk])
        self.assertEqual(
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(first.pk),
            ).pk,
            first.pk,
        )
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(second.pk),
            )

    def test_ended_episode_requires_current_same_person_and_history_policy(self):
        old = self._relationship(
            self.person,
            "E-OLD",
            start=self.today - timedelta(days=120),
            end=self.today - timedelta(days=40),
        )
        document = self._document(old)
        self._allow(current=True, history=False)
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
            )
        self._allow(current=True, history=True)
        self.assertEqual(
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
            ).document.pk,
            document.pk,
        )
        from apps.workforce.person_services import end_work_relationship

        end_work_relationship(
            organization=self.organization,
            actor=self.owner,
            relationship=self.relationship,
            effective_end=self.today - timedelta(days=1),
        )
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
            )

    def test_cross_person_and_cross_tenant_direct_urls_do_not_disclose(self):
        document = self._document()
        self._allow(current=True, download=True)
        self._scan_clean(document.current_version)
        self.assertEqual(
            get_employee_documents(
                user=self.other_user, organization=self.organization
            ),
            [],
        )
        self._client_as(self.other_user)
        detail_url = reverse(
            "documents:employee-detail", kwargs={"document_id": document.pk}
        )
        download_url = reverse(
            "documents:employee-version-download",
            kwargs={
                "document_id": document.pk,
                "version_id": document.current_version_id,
            },
        )
        self.assertEqual(self.client.get(detail_url).status_code, 403)
        self.assertEqual(self.client.get(download_url).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("documents:employee-list")).status_code, 200
        )
        other_organization = Organization.objects.create(
            name="Other tenant",
            slug="cep011-other-tenant",
            created_by=self.owner,
            updated_by=self.owner,
        )
        OrganizationSettings.objects.create(organization=other_organization)
        other_membership = OrganizationMembership.objects.create(
            organization=other_organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            role_definition=OrganizationRole.objects.get(code="cep011_setup"),
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=other_organization,
            membership=other_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-011 other tenant",
        )
        other_person = create_person(
            organization=other_organization,
            actor=self.owner,
            first_name="Other",
            last_name="Tenant",
            user=self.owner,
        )
        other_relationship = create_work_relationship(
            organization=other_organization,
            actor=self.owner,
            person=other_person,
            employee_number="OT-1",
            effective_start=self.today - timedelta(days=2),
        )
        other_category = create_document_category(
            organization=other_organization,
            actor=self.owner,
            code="other",
            name="Other",
        )
        other_document = create_document(
            organization=other_organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Other tenant evidence",
            upload=self._upload(),
            target=other_relationship,
            category=other_category,
        )
        cross_url = reverse(
            "documents:employee-detail", kwargs={"document_id": other_document.pk}
        )
        self.assertEqual(self.client.get(cross_url).status_code, 403)
        with self.assertRaises(ValidationError):
            create_typed_link(
                organization=self.organization,
                document=document,
                target_type="work_relationship",
                target=other_relationship,
                created_by=self.owner,
            )

    def test_source_scope_and_legacy_ambiguity_fail_closed(self):
        document = self._document()
        self._allow(current=True, history=True)
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="CEP011-P",
            name="Restricted project",
        )
        add_document_link(document=document, actor=self.owner, target=project)
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
            )
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="E-LEGACY",
            first_name="Test",
            last_name="Employee",
        )
        qualification = EmployeeQualification.objects.create(
            organization=self.organization,
            employee=employee,
            kind=QualificationKind.CERTIFICATE,
            title="Certificate",
            recorded_by=self.owner,
        )
        evidence = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Qualification evidence",
            upload=self._upload(),
            target=qualification,
            category=self.category,
        )
        self.assertEqual(
            get_organization_document(
                user=self.owner,
                organization=self.organization,
                document_id=str(evidence.pk),
            ).pk,
            evidence.pk,
        )
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(evidence.pk),
            )
        self._relationship(
            self.person,
            "E-LEGACY",
            start=self.today - timedelta(days=200),
            end=self.today - timedelta(days=150),
            legacy=employee,
        )
        self.assertEqual(
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(evidence.pk),
            ).document.pk,
            evidence.pk,
        )
        self._relationship(
            self.person,
            "E-LEGACY",
            start=self.today - timedelta(days=300),
            end=self.today - timedelta(days=250),
            legacy=employee,
        )
        with self.assertRaises(PermissionDenied):
            get_employee_document(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(evidence.pk),
            )

    def test_employee_ui_download_reauthorizes(self):
        document = self._document()
        self._allow(current=True, download=True)
        with self.assertRaises(PermissionDenied):
            get_employee_version_for_download(
                user=self.employee_user,
                organization=self.organization,
                document_id=str(document.pk),
                version_id=str(document.current_version_id),
            )
        self._scan_clean(document.current_version)
        self._client_as(self.employee_user)
        detail_url = reverse(
            "documents:employee-detail", kwargs={"document_id": document.pk}
        )
        download_url = reverse(
            "documents:employee-version-download",
            kwargs={
                "document_id": document.pk,
                "version_id": document.current_version_id,
            },
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "work_relationship")
        self.assertContains(detail, "دریافت")
        with patch(
            "apps.documents.views._download_response", return_value=HttpResponse()
        ) as response_builder:
            response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        response_builder.assert_called_once()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DOCUMENT_DOWNLOADED,
                entity_id=str(document.pk),
            ).exists()
        )
        self._allow(current=False, history=False, download=True)
        self.assertEqual(self.client.get(detail_url).status_code, 403)
        self.assertEqual(self.client.get(download_url).status_code, 403)
