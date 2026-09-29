from datetime import timedelta

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.daily_reports.models import DailyReport
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty, PartyKind
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite, WBSNode
from apps.quality.models import (
    QualityIssue,
    QualityIssueSeverity,
    QualityIssueStatus,
    QualityIssueType,
)
from apps.quality.services import (
    assign_quality_issue,
    close_quality_issue,
    create_quality_issue,
    get_organization_quality_issue,
    get_organization_quality_issues,
    review_quality_issue,
    start_quality_corrective_action,
    submit_quality_issue_for_verification,
    verify_quality_issue,
)
from apps.workforce.models import Employee


class QualityTestBase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="quality-owner")
        self.viewer = User.objects.create_user(username="quality-viewer")
        self.other_owner = User.objects.create_user(username="other-quality-owner")
        self.organization = Organization.objects.create(
            name="Quality Co", slug="quality-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Quality Co", slug="other-quality-co"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, timezone="Asia/Tehran"
        )
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="QUAL-P", name="Quality Project"
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="MAIN",
            name="Main Site",
        )
        self.phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=self.site,
            code="FOUND",
            name="Foundation",
        )
        self.wbs = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            code="01",
            title="Foundation",
        )
        self.activity = Activity.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            wbs_node=self.wbs,
            code="CONC",
            name="Concrete",
        )
        self.daily_report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            reporting_date=timezone.localdate(),
            work_performed="Concrete placement",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="E-1",
            first_name="Ali",
            last_name="Ahmadi",
        )
        self.party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind=PartyKind.COMPANY,
            display_name="Quality Subcontractor",
        )

    def create_issue(self, number: str = "QI-001") -> QualityIssue:
        return create_quality_issue(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            phase=self.phase,
            activity=self.activity,
            daily_report=self.daily_report,
            issue_number=number,
            identified_at=timezone.now() - timedelta(minutes=5),
            issue_type=QualityIssueType.NONCONFORMANCE,
            severity=QualityIssueSeverity.MAJOR,
            description="Concrete surface has unacceptable honeycombing",
            specification_reference="SPEC-CONC-04",
        )

    def close_issue(self, issue: QualityIssue) -> QualityIssue:
        review_quality_issue(
            organization=self.organization, actor=self.owner, issue_id=issue.pk
        )
        assign_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            due_date=timezone.localdate() + timedelta(days=3),
            responsible_employee=self.employee,
        )
        start_quality_corrective_action(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action="Remove unsound concrete and repair with approved mortar",
        )
        submit_quality_issue_for_verification(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            corrective_action_result="Repair completed and cured",
        )
        verify_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            verification_summary="Visual inspection and rebound test accepted",
        )
        return close_quality_issue(
            organization=self.organization,
            actor=self.owner,
            issue_id=issue.pk,
            closure_summary="Consultant acceptance recorded",
        )


class QualityIssueModelTests(QualityTestBase):
    def test_closed_issue_cannot_be_changed_or_deleted(self) -> None:
        issue = self.close_issue(self.create_issue())
        issue.description = "Destructive edit"
        with self.assertRaises(ValidationError):
            issue.save()
        with self.assertRaises(ValidationError):
            issue.delete()
        with self.assertRaises(ValidationError):
            QualityIssue.objects.filter(pk=issue.pk).update(description="Bypass")

    def test_status_cannot_be_changed_outside_service(self) -> None:
        issue = self.create_issue()
        issue.status = QualityIssueStatus.UNDER_REVIEW
        issue.reviewed_at = timezone.now()
        issue.reviewed_by = self.owner
        with self.assertRaises(ValidationError):
            issue.save()


class QualityIssueServiceTests(QualityTestBase):
    def test_create_read_rbac_tenant_scope_and_audit(self) -> None:
        issue = self.create_issue("qi-100")
        self.assertEqual(issue.issue_number, "QI-100")
        self.assertEqual(
            list(
                get_organization_quality_issues(
                    user=self.viewer, organization=self.organization
                )
            ),
            [issue],
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.QUALITY_ISSUE_CREATED,
                entity_id=str(issue.pk),
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            create_quality_issue(
                organization=self.organization,
                actor=self.viewer,
                project=self.project,
                issue_number="DENIED",
                identified_at=timezone.now(),
                issue_type=QualityIssueType.OTHER,
                severity=QualityIssueSeverity.MINOR,
                description="Denied",
            )

    def test_full_lifecycle_is_ordered_and_audited(self) -> None:
        issue = self.close_issue(self.create_issue())
        self.assertEqual(issue.status, QualityIssueStatus.CLOSED)
        self.assertEqual(issue.closed_by, self.owner)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_type="quality_issue",
                entity_id=str(issue.pk),
            ).count(),
            7,
        )
        with self.assertRaises(ValueError):
            review_quality_issue(
                organization=self.organization,
                actor=self.owner,
                issue_id=issue.pk,
            )

    def test_cross_tenant_and_structurally_inconsistent_relations_are_rejected(
        self,
    ) -> None:
        other_project = Project.objects.create(
            organization=self.other_organization, code="OTHER", name="Other Project"
        )
        with self.assertRaises(PermissionDenied):
            create_quality_issue(
                organization=self.organization,
                actor=self.owner,
                project=other_project,
                issue_number="QI-X",
                identified_at=timezone.now(),
                issue_type=QualityIssueType.DEFECT,
                severity=QualityIssueSeverity.MAJOR,
                description="Invalid tenant",
            )

        second_project = Project.objects.create(
            organization=self.organization, code="SECOND", name="Second Project"
        )
        second_site = ProjectSite.objects.create(
            organization=self.organization,
            project=second_project,
            code="SECOND",
            name="Second Site",
        )
        with self.assertRaises(ValueError):
            create_quality_issue(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                site=second_site,
                issue_number="QI-Y",
                identified_at=timezone.now(),
                issue_type=QualityIssueType.DEFECT,
                severity=QualityIssueSeverity.MAJOR,
                description="Invalid structure",
            )

    def test_phase_activity_and_daily_report_must_match_project_structure(
        self,
    ) -> None:
        second_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="SECOND-SITE",
            name="Second Site",
        )
        second_phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=second_site,
            code="SECOND-PHASE",
            name="Second Phase",
        )
        second_activity = Activity.objects.create(
            organization=self.organization,
            project=self.project,
            site=second_site,
            phase=second_phase,
            wbs_node=self.wbs,
            code="SECOND-ACT",
            name="Second Activity",
        )
        second_report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=second_site,
            phase=second_phase,
            reporting_date=timezone.localdate(),
            work_performed="Second site work",
            created_by=self.owner,
            updated_by=self.owner,
        )
        invalid_relations = (
            {"site": self.site, "phase": second_phase},
            {"site": self.site, "phase": self.phase, "activity": second_activity},
            {"site": self.site, "phase": self.phase, "daily_report": second_report},
        )
        for index, relations in enumerate(invalid_relations, start=1):
            with self.subTest(relation=index), self.assertRaises(ValueError):
                create_quality_issue(
                    organization=self.organization,
                    actor=self.owner,
                    project=self.project,
                    issue_number=f"QI-S-{index}",
                    identified_at=timezone.now(),
                    issue_type=QualityIssueType.DEFECT,
                    severity=QualityIssueSeverity.MAJOR,
                    description="Invalid project structure",
                    **relations,
                )

    def test_cross_tenant_responsible_relations_are_rejected(self) -> None:
        other_employee = Employee.objects.create(
            organization=self.other_organization,
            employee_number="OE-1",
            first_name="Other",
            last_name="Employee",
        )
        other_party = BusinessParty.objects.create(
            organization=self.other_organization,
            party_kind=PartyKind.COMPANY,
            display_name="Other Party",
        )
        for index, responsible in enumerate(
            (
                {"responsible_user": self.other_owner},
                {"responsible_employee": other_employee},
                {"responsible_party": other_party},
            ),
            start=1,
        ):
            issue = self.create_issue(f"QI-R-{index}")
            review_quality_issue(
                organization=self.organization, actor=self.owner, issue_id=issue.pk
            )
            with (
                self.subTest(responsible=next(iter(responsible))),
                self.assertRaises(PermissionDenied),
            ):
                assign_quality_issue(
                    organization=self.organization,
                    actor=self.owner,
                    issue_id=issue.pk,
                    due_date=timezone.localdate() + timedelta(days=3),
                    **responsible,
                )

    def test_detail_does_not_disclose_another_tenant(self) -> None:
        issue = self.create_issue()
        with self.assertRaises(PermissionDenied):
            get_organization_quality_issue(
                user=self.other_owner,
                organization=self.other_organization,
                issue_id=issue.pk,
            )


class QualityIssueViewAndAdminTests(QualityTestBase):
    def test_create_view_relations_are_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        other_project = Project.objects.create(
            organization=self.other_organization,
            code="HIDDEN",
            name="Hidden Quality Project",
        )
        response = self.client.get(reverse("quality:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, other_project.name)

    def test_admin_is_read_only(self) -> None:
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        model_admin = admin.site._registry[QualityIssue]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
