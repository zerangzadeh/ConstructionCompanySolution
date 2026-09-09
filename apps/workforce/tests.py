from datetime import date

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import (
    AssignmentStatus,
    Department,
    Employee,
    EmployeeProjectAssignment,
    EmployeeStatus,
    Position,
    WorkTeam,
)
from apps.workforce.services import (
    archive_department,
    archive_employee,
    assign_employee_to_project,
    create_department,
    create_employee,
    create_position,
    create_work_team,
    get_organization_employees,
    get_organization_project_assignments,
    transition_employee_status,
    transition_project_assignment_status,
)


class WorkforceModelTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="workforce-owner")
        self.other_owner = User.objects.create_user(username="other-workforce-owner")
        self.organization = Organization.objects.create(
            name="Workforce Co", slug="workforce-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Workforce Co", slug="other-workforce-co"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="WF", name="Workforce Project"
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="MAIN",
            name="Main Site",
        )

    def test_employee_is_distinct_from_optional_active_member_user(self) -> None:
        employee_without_user = Employee.objects.create(
            organization=self.organization,
            employee_number="emp-001",
            first_name="Ada",
            last_name="Lovelace",
        )
        employee_with_user = Employee.objects.create(
            organization=self.organization,
            user=self.owner,
            employee_number="emp-002",
            first_name="Grace",
            last_name="Hopper",
        )

        self.assertIsNone(employee_without_user.user)
        self.assertEqual(employee_with_user.user, self.owner)
        self.assertEqual(employee_without_user.employee_number, "EMP-001")

        with self.assertRaises(ValidationError):
            Employee.objects.create(
                organization=self.organization,
                user=self.other_owner,
                employee_number="EMP-003",
                first_name="Cross",
                last_name="Tenant",
            )

    def test_employee_number_and_linked_user_are_unique_per_tenant(self) -> None:
        Employee.objects.create(
            organization=self.organization,
            user=self.owner,
            employee_number="EMP-001",
            first_name="First",
            last_name="Employee",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Employee.objects.create(
                organization=self.organization,
                employee_number="emp-001",
                first_name="Duplicate",
                last_name="Number",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Employee.objects.create(
                organization=self.organization,
                user=self.owner,
                employee_number="EMP-002",
                first_name="Duplicate",
                last_name="User",
            )

        other = Employee.objects.create(
            organization=self.other_organization,
            user=self.other_owner,
            employee_number="EMP-001",
            first_name="Other",
            last_name="Tenant",
        )
        self.assertEqual(other.employee_number, "EMP-001")

    def test_workforce_relations_reject_cross_tenant_records(self) -> None:
        other_department = Department.objects.create(
            organization=self.other_organization,
            code="OPS",
            name="Other Operations",
        )
        other_position = Position.objects.create(
            organization=self.other_organization,
            code="ENG",
            title="Other Engineer",
        )
        other_employee = Employee.objects.create(
            organization=self.other_organization,
            employee_number="OTHER-1",
            first_name="Other",
            last_name="Employee",
        )
        other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Other Project",
        )

        invalid_records = [
            Department(
                organization=self.organization,
                parent=other_department,
                code="BAD",
                name="Bad Department",
            ),
            Position(
                organization=self.organization,
                department=other_department,
                code="BAD",
                title="Bad Position",
            ),
            WorkTeam(
                organization=self.organization,
                lead=other_employee,
                code="BAD",
                name="Bad Team",
            ),
            Employee(
                organization=self.organization,
                position=other_position,
                employee_number="BAD",
                first_name="Bad",
                last_name="Employee",
            ),
            EmployeeProjectAssignment(
                organization=self.organization,
                employee=other_employee,
                project=self.project,
                start_date=date(2026, 9, 1),
            ),
            EmployeeProjectAssignment(
                organization=self.organization,
                employee=Employee.objects.create(
                    organization=self.organization,
                    employee_number="LOCAL",
                    first_name="Local",
                    last_name="Employee",
                ),
                project=other_project,
                start_date=date(2026, 9, 1),
            ),
        ]

        for record in invalid_records:
            with (
                self.subTest(model=record.__class__.__name__),
                self.assertRaises(ValidationError),
            ):
                record.save()

    def test_department_cycles_and_mismatched_position_are_rejected(self) -> None:
        department = Department.objects.create(
            organization=self.organization, code="OPS", name="Operations"
        )
        child = Department.objects.create(
            organization=self.organization,
            parent=department,
            code="SITE",
            name="Site Operations",
        )
        department.parent = child
        with self.assertRaises(ValidationError):
            department.save()

        position = Position.objects.create(
            organization=self.organization,
            department=child,
            code="ENG",
            title="Site Engineer",
        )
        with self.assertRaises(ValidationError):
            Employee.objects.create(
                organization=self.organization,
                department=department,
                position=position,
                employee_number="EMP-004",
                first_name="Wrong",
                last_name="Department",
            )

    def test_employee_and_assignment_lifecycle_dates_are_validated(self) -> None:
        with self.assertRaises(ValidationError):
            Employee.objects.create(
                organization=self.organization,
                employee_number="EMP-005",
                first_name="Missing",
                last_name="Date",
                status=EmployeeStatus.TERMINATED,
            )
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="EMP-006",
            first_name="Assigned",
            last_name="Employee",
        )
        with self.assertRaises(ValidationError):
            EmployeeProjectAssignment.objects.create(
                organization=self.organization,
                employee=employee,
                project=self.project,
                site=self.site,
                start_date=date(2026, 9, 2),
                end_date=date(2026, 9, 1),
                status=AssignmentStatus.COMPLETED,
            )

        assignment = EmployeeProjectAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            project=self.project,
            site=self.site,
            start_date=date(2026, 9, 1),
        )
        self.assertEqual(assignment.status, AssignmentStatus.ACTIVE)

        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeProjectAssignment.objects.create(
                organization=self.organization,
                employee=employee,
                project=self.project,
                site=self.site,
                start_date=date(2026, 9, 2),
            )


class WorkforceServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="service-workforce-owner")
        self.viewer = User.objects.create_user(username="service-workforce-viewer")
        self.outsider = User.objects.create_user(username="service-workforce-outsider")
        self.organization = Organization.objects.create(
            name="Service Workforce Co", slug="service-workforce-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Service Workforce Co", slug="other-service-workforce-co"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="SERVICE", name="Service Project"
        )

    def test_create_workforce_structure_employee_and_assignment_are_audited(
        self,
    ) -> None:
        department = create_department(
            organization=self.organization,
            actor=self.owner,
            code="ops",
            name="Operations",
        )
        position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="engineer",
            title="Engineer",
            department=department,
        )
        team = create_work_team(
            organization=self.organization,
            actor=self.owner,
            code="alpha",
            name="Alpha",
            department=department,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="e-001",
            first_name="Ava",
            last_name="Builder",
            department=department,
            position=position,
            work_team=team,
        )
        assignment = assign_employee_to_project(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            project=self.project,
            start_date=date(2026, 9, 1),
            role_title="Site engineer",
        )

        self.assertEqual(assignment.organization, self.organization)
        self.assertEqual(
            set(
                AuditEvent.objects.filter(organization=self.organization).values_list(
                    "action", flat=True
                )
            ),
            {
                AuditAction.DEPARTMENT_CREATED,
                AuditAction.POSITION_CREATED,
                AuditAction.WORK_TEAM_CREATED,
                AuditAction.EMPLOYEE_CREATED,
                AuditAction.EMPLOYEE_PROJECT_ASSIGNED,
            },
        )

    def test_small_tenant_can_create_employee_without_structure_or_user(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="solo",
            first_name="Solo",
            last_name="Worker",
        )

        self.assertIsNone(employee.user)
        self.assertIsNone(employee.department)
        self.assertIsNone(employee.position)
        self.assertIsNone(employee.work_team)

    def test_viewer_can_read_but_cannot_mutate_workforce(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="readable",
            first_name="Readable",
            last_name="Employee",
        )
        self.assertEqual(
            list(
                get_organization_employees(
                    user=self.viewer, organization=self.organization
                )
            ),
            [employee],
        )
        with self.assertRaises(PermissionDenied):
            create_department(
                organization=self.organization,
                actor=self.viewer,
                code="NO",
                name="Forbidden",
            )

    def test_reads_and_mutations_enforce_tenant_scope(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="local",
            first_name="Local",
            last_name="Employee",
        )
        other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Other Project",
        )
        with self.assertRaises(PermissionDenied):
            get_organization_employees(
                user=self.outsider, organization=self.organization
            )
        with self.assertRaises(PermissionDenied):
            assign_employee_to_project(
                organization=self.organization,
                actor=self.owner,
                employee=employee,
                project=other_project,
                start_date=date(2026, 9, 1),
            )
        self.assertFalse(
            get_organization_project_assignments(
                user=self.owner, organization=self.organization
            )
            .filter(project=other_project)
            .exists()
        )

    def test_employee_and_assignment_transitions_are_atomic_and_audited(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="transition",
            first_name="Transition",
            last_name="Employee",
            hire_date=date(2026, 1, 1),
        )
        assignment = assign_employee_to_project(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            project=self.project,
            start_date=date(2026, 9, 1),
        )
        completed = transition_project_assignment_status(
            organization=self.organization,
            actor=self.owner,
            assignment=assignment,
            target_status=AssignmentStatus.COMPLETED,
            end_date=date(2026, 9, 30),
        )
        terminated = transition_employee_status(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            target_status=EmployeeStatus.TERMINATED,
            effective_date=date(2026, 10, 1),
        )

        self.assertEqual(completed.status, AssignmentStatus.COMPLETED)
        self.assertEqual(terminated.termination_date, date(2026, 10, 1))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.EMPLOYEE_STATUS_CHANGED,
                entity_id=str(employee.pk),
            ).exists()
        )
        with self.assertRaises(ValueError):
            transition_employee_status(
                organization=self.organization,
                actor=self.owner,
                employee=terminated,
                target_status=EmployeeStatus.ACTIVE,
            )

    def test_archival_preserves_records_and_blocks_active_dependencies(self) -> None:
        department = create_department(
            organization=self.organization,
            actor=self.owner,
            code="ARCH",
            name="Archive Department",
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="archive",
            first_name="Archive",
            last_name="Employee",
            department=department,
        )
        with self.assertRaises(ValueError):
            archive_department(
                organization=self.organization,
                actor=self.owner,
                department=department,
            )
        archived = archive_employee(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
        )
        archived_department = archive_department(
            organization=self.organization,
            actor=self.owner,
            department=department,
        )

        self.assertIsNotNone(archived.archived_at)
        self.assertIsNotNone(archived_department.archived_at)
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())


class WorkforceAdminTests(TestCase):
    def test_workforce_admin_is_read_only(self) -> None:
        request = RequestFactory().get("/admin/")
        for model in (
            Department,
            Position,
            WorkTeam,
            Employee,
            EmployeeProjectAssignment,
        ):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
