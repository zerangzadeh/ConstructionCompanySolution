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
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty, PartyKind
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite, WBSNode
from apps.safety.models import (
    SafetyIncident,
    SafetyIncidentSeverity,
    SafetyIncidentStatus,
    SafetyIncidentType,
)
from apps.safety.services import (
    assign_safety_incident,
    close_safety_incident,
    create_safety_incident,
    get_organization_safety_incident,
    get_organization_safety_incidents,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from apps.workforce.models import Employee


class SafetyTestBase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="safety-owner")
        self.viewer = User.objects.create_user(username="safety-viewer")
        self.other_owner = User.objects.create_user(username="other-safety-owner")
        self.organization = Organization.objects.create(
            name="Safety Co", slug="safety-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Safety Co", slug="other-safety-co"
        )
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
            organization=self.organization, code="SAFE-P", name="Safety Project"
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
            code="EXC",
            name="Excavation",
        )
        self.daily_report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            reporting_date=timezone.localdate(),
            work_performed="Excavation",
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
            display_name="Safety Subcontractor",
        )

    def create_incident(self, number: str = "SI-001") -> SafetyIncident:
        return create_safety_incident(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            phase=self.phase,
            activity=self.activity,
            daily_report=self.daily_report,
            incident_number=number,
            occurred_at=timezone.now() - timedelta(minutes=5),
            incident_type=SafetyIncidentType.NEAR_MISS,
            severity=SafetyIncidentSeverity.HIGH,
            description="Falling object near miss",
            immediate_action="Area isolated",
        )


class SafetyIncidentModelTests(SafetyTestBase):
    def test_structural_relations_reject_cross_tenant_project(self) -> None:
        other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Other Project",
        )
        with self.assertRaises(PermissionDenied):
            create_safety_incident(
                organization=self.organization,
                actor=self.owner,
                project=other_project,
                incident_number="SI-X",
                occurred_at=timezone.now(),
                incident_type=SafetyIncidentType.INJURY,
                severity=SafetyIncidentSeverity.MEDIUM,
                description="Invalid scope",
            )

    def test_closed_incident_cannot_be_changed_or_deleted(self) -> None:
        incident = self.create_incident()
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            due_date=timezone.localdate() + timedelta(days=3),
            responsible_employee=self.employee,
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            corrective_action="Install toe boards",
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            resolution_summary="Toe boards installed and inspected",
        )
        close_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            closure_summary="Controls verified",
        )
        incident.refresh_from_db()
        incident.description = "Destructive edit"
        with self.assertRaises(ValidationError):
            incident.save()
        with self.assertRaises(ValidationError):
            incident.delete()
        with self.assertRaises(ValidationError):
            SafetyIncident.objects.filter(pk=incident.pk).update(description="Bypass")


class SafetyIncidentServiceTests(SafetyTestBase):
    def test_create_read_rbac_tenant_scope_and_audit(self) -> None:
        incident = self.create_incident("si-100")
        self.assertEqual(incident.incident_number, "SI-100")
        self.assertEqual(
            list(
                get_organization_safety_incidents(
                    user=self.viewer, organization=self.organization
                )
            ),
            [incident],
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.SAFETY_INCIDENT_CREATED,
                entity_id=str(incident.pk),
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            create_safety_incident(
                organization=self.organization,
                actor=self.viewer,
                project=self.project,
                incident_number="DENIED",
                occurred_at=timezone.now(),
                incident_type=SafetyIncidentType.OTHER,
                severity=SafetyIncidentSeverity.LOW,
                description="Denied",
            )

    def test_full_lifecycle_is_ordered_and_audited(self) -> None:
        incident = self.create_incident()
        review_safety_incident(
            organization=self.organization, actor=self.owner, incident_id=incident.pk
        )
        assign_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            due_date=timezone.localdate() + timedelta(days=3),
            responsible_user=self.owner,
            responsible_employee=self.employee,
            responsible_party=self.party,
        )
        start_corrective_action(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            corrective_action="Install guard and brief crew",
        )
        resolve_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            resolution_summary="Guard installed and crew briefed",
        )
        closed = close_safety_incident(
            organization=self.organization,
            actor=self.owner,
            incident_id=incident.pk,
            closure_summary="Site manager verified controls",
        )
        self.assertEqual(closed.status, SafetyIncidentStatus.CLOSED)
        self.assertEqual(closed.closed_by, self.owner)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_type="safety_incident",
                entity_id=str(incident.pk),
            ).count(),
            6,
        )
        with self.assertRaises(ValueError):
            review_safety_incident(
                organization=self.organization,
                actor=self.owner,
                incident_id=incident.pk,
            )

    def test_detail_does_not_disclose_another_tenant(self) -> None:
        incident = self.create_incident()
        with self.assertRaises(PermissionDenied):
            get_organization_safety_incident(
                user=self.other_owner,
                organization=self.other_organization,
                incident_id=incident.pk,
            )


class SafetyIncidentViewAndAdminTests(SafetyTestBase):
    def test_list_and_create_views_are_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        other_project = Project.objects.create(
            organization=self.other_organization,
            code="HIDDEN",
            name="Hidden Safety Project",
        )
        response = self.client.get(reverse("safety:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, other_project.name)

    def test_admin_is_read_only(self) -> None:
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        model_admin = admin.site._registry[SafetyIncident]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
