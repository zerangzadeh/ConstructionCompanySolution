import tempfile
from datetime import date
from io import StringIO

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project, ProjectSite
from apps.workforce.forms import EmployeeAssignmentForm
from apps.workforce.models import (
    AssignmentStatus,
    Department,
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    EmployeeStatus,
    Position,
    PositionAssignmentStatus,
    WorkTeam,
)
from apps.workforce.services import (
    archive_department,
    archive_employee,
    archive_position,
    assign_employee_position,
    assign_employee_to_project,
    create_department,
    create_employee,
    create_employee_from_member,
    create_position,
    create_work_team,
    end_employee_position,
    get_active_chief_executive,
    get_employee_position_assignments,
    get_organization_employees,
    get_organization_project_assignments,
    link_employee_account,
    transition_employee_status,
    transition_project_assignment_status,
    unlink_employee_account,
    update_employee_profile_image,
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
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
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

    def test_project_assignment_uses_responsibility_label(self) -> None:
        form = EmployeeAssignmentForm(organization=self.organization)

        self.assertEqual(form.fields["role_title"].label, "مسئولیت در پروژه")

    def test_employee_rejects_a_spoofed_profile_image(self) -> None:
        employee = Employee(
            organization=self.organization,
            employee_number="INVALID-IMAGE",
            first_name="Invalid",
            last_name="Image",
            profile_image=SimpleUploadedFile(
                "profile.png",
                b"not-a-real-png",
                content_type="image/png",
            ),
        )

        with self.assertRaises(ValidationError):
            employee.full_clean()

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
            EmployeePositionAssignment(
                organization=self.organization,
                employee=other_employee,
                position=Position.objects.create(
                    organization=self.organization,
                    code="LOCAL-POSITION",
                    title="Local Position",
                ),
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

    def test_position_parent_rejects_cross_tenant_self_and_cycles(self) -> None:
        parent = Position.objects.create(
            organization=self.organization, code="DIRECTOR", title="Director"
        )
        child = Position.objects.create(
            organization=self.organization,
            parent_position=parent,
            code="MANAGER",
            title="Manager",
        )
        self_parent = Position.objects.create(
            organization=self.organization, code="SELF", title="Self"
        )
        self_parent.parent_position = self_parent
        with self.assertRaises(ValidationError):
            self_parent.save()

        parent.parent_position = child
        with self.assertRaises(ValidationError):
            parent.save()

        foreign_parent = Position.objects.create(
            organization=self.other_organization,
            code="FOREIGN-DIRECTOR",
            title="Foreign Director",
        )
        with self.assertRaises(ValidationError):
            Position.objects.create(
                organization=self.organization,
                parent_position=foreign_parent,
                code="FOREIGN-CHILD",
                title="Foreign Child",
            ).save()

    def test_position_parent_must_be_active_and_position_with_active_child_cannot_archive(
        self,
    ) -> None:
        parent = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PARENT",
            title="Parent",
        )
        child = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CHILD",
            title="Child",
            parent_position=parent,
        )
        with self.assertRaises(ValueError):
            archive_position(
                organization=self.organization, actor=self.owner, position=parent
            )

        child.is_active = False
        child.save()
        archive_position(
            organization=self.organization, actor=self.owner, position=parent
        )
        inactive_parent = Position.objects.create(
            organization=self.organization,
            code="INACTIVE-PARENT",
            title="Inactive Parent",
            is_active=False,
        )
        with self.assertRaises(ValueError):
            create_position(
                organization=self.organization,
                actor=self.owner,
                code="INVALID-CHILD",
                title="Invalid Child",
                parent_position=inactive_parent,
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

    def test_position_assignment_dates_and_active_uniqueness_are_enforced(self) -> None:
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="MULTI-001",
            first_name="Multi",
            last_name="Position",
        )
        position = Position.objects.create(
            organization=self.organization,
            code="ENGINEER",
            title="Engineer",
        )
        EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=employee,
            position=position,
            start_date=date(2026, 9, 1),
            is_primary=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeePositionAssignment.objects.create(
                organization=self.organization,
                employee=employee,
                position=position,
                start_date=date(2026, 9, 2),
            )
        with self.assertRaises(ValidationError):
            EmployeePositionAssignment.objects.create(
                organization=self.organization,
                employee=employee,
                position=Position.objects.create(
                    organization=self.organization,
                    code="INVALID-DATE",
                    title="Invalid Date",
                ),
                start_date=date(2026, 9, 2),
                end_date=date(2026, 9, 1),
                status=PositionAssignmentStatus.ENDED,
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
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
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
                AuditAction.EMPLOYEE_POSITION_ASSIGNED,
                AuditAction.EMPLOYEE_PROJECT_ASSIGNED,
            },
        )

    def test_owner_links_and_unlinks_only_an_active_tenant_member(self) -> None:
        member = User.objects.create_user(username="employee-account-member")
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="LINK-1",
            first_name="Linked",
            last_name="Employee",
        )

        linked = link_employee_account(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            user=member,
        )
        self.assertEqual(linked.user, member)
        unlinked = unlink_employee_account(
            organization=self.organization, actor=self.owner, employee=linked
        )
        self.assertIsNone(unlinked.user)
        self.assertEqual(
            set(
                AuditEvent.objects.filter(
                    organization=self.organization,
                    entity_id=str(employee.pk),
                    action__in=(
                        AuditAction.EMPLOYEE_ACCOUNT_LINKED,
                        AuditAction.EMPLOYEE_ACCOUNT_UNLINKED,
                    ),
                ).values_list("action", flat=True)
            ),
            {
                AuditAction.EMPLOYEE_ACCOUNT_LINKED,
                AuditAction.EMPLOYEE_ACCOUNT_UNLINKED,
            },
        )

    def test_employee_account_link_rejects_a_foreign_tenant_user(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="LINK-FOREIGN",
            first_name="Local",
            last_name="Employee",
        )

        with self.assertRaises(PermissionDenied):
            link_employee_account(
                organization=self.organization,
                actor=self.owner,
                employee=employee,
                user=self.outsider,
            )

    def test_employee_profile_image_update_is_tenant_scoped_and_audited(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PROFILE-IMAGE-001",
            first_name="Profile",
            last_name="Image",
        )
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            updated = update_employee_profile_image(
                organization=self.organization,
                actor=self.owner,
                employee=employee,
                data={
                    "profile_image": SimpleUploadedFile(
                        "employee.png",
                        b"\x89PNG\r\n\x1a\n" + b"employee-profile-data",
                        content_type="image/png",
                    )
                },
            )

            self.assertTrue(
                updated.profile_image.name.startswith(
                    f"organizations/{self.organization.pk}/employees/{employee.pk}/"
                )
            )
            self.assertTrue(
                AuditEvent.objects.filter(
                    organization=self.organization,
                    entity_id=str(employee.pk),
                    action=AuditAction.EMPLOYEE_PROFILE_IMAGE_UPDATED,
                ).exists()
            )

    def test_employee_can_hold_multiple_positions_and_change_primary(self) -> None:
        first_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="TECHNICAL",
            title="Technical Manager",
        )
        second_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="SAFETY",
            title="Safety Manager",
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="MULTI-SERVICE-001",
            first_name="Multiple",
            last_name="Roles",
            position=first_position,
            hire_date=date(2026, 9, 1),
        )

        second_assignment = assign_employee_position(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            position=second_position,
            start_date=date(2026, 9, 2),
            is_primary=True,
        )

        employee.refresh_from_db()
        assignments = get_employee_position_assignments(
            user=self.owner,
            organization=self.organization,
            employee=employee,
        )
        self.assertEqual(assignments.filter(status="active").count(), 2)
        self.assertEqual(assignments.filter(is_primary=True).get(), second_assignment)
        self.assertEqual(employee.position, second_position)

    def test_single_holder_position_rejects_a_second_active_employee(self) -> None:
        ceo = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CEO",
            title="Chief Executive Officer",
            is_single_holder=True,
        )
        first_employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="CEO-001",
            first_name="First",
            last_name="Executive",
            position=ceo,
        )
        second_employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="CEO-002",
            first_name="Second",
            last_name="Executive",
        )

        with self.assertRaisesMessage(ValueError, "متصدی فعال"):
            assign_employee_position(
                organization=self.organization,
                actor=self.owner,
                employee=second_employee,
                position=ceo,
                start_date=date(2026, 9, 2),
            )

        self.assertEqual(
            first_employee.position_assignments.filter(status="active").count(), 1
        )
        self.assertEqual(
            get_active_chief_executive(
                user=self.owner,
                organization=self.organization,
            ),
            first_employee,
        )

    def test_job_position_does_not_grant_system_workflow_permission(self) -> None:
        ceo = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CEO-AUTH",
            title="Chief Executive Officer",
            is_single_holder=True,
        )
        create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="CEO-AUTH-001",
            first_name="Viewer",
            last_name="Executive",
            user=self.viewer,
            position=ceo,
        )

        self.assertFalse(
            has_business_permission(
                user=self.viewer,
                organization=self.organization,
                permission=BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE,
            )
        )

    def test_ending_primary_position_promotes_remaining_active_position(self) -> None:
        primary = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PRIMARY",
            title="Primary Position",
        )
        secondary = create_position(
            organization=self.organization,
            actor=self.owner,
            code="SECONDARY",
            title="Secondary Position",
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PROMOTE-001",
            first_name="Primary",
            last_name="Holder",
            position=primary,
        )
        primary_assignment = employee.position_assignments.get(position=primary)
        secondary_assignment = assign_employee_position(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            position=secondary,
            start_date=date(2026, 9, 2),
        )

        ended = end_employee_position(
            organization=self.organization,
            actor=self.owner,
            assignment=primary_assignment,
            end_date=date(2026, 9, 3),
        )

        employee.refresh_from_db()
        secondary_assignment.refresh_from_db()
        self.assertEqual(ended.status, PositionAssignmentStatus.ENDED)
        self.assertEqual(employee.position, secondary)
        self.assertTrue(secondary_assignment.is_primary)

    def test_position_assignment_service_rejects_cross_tenant_employee(self) -> None:
        position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="LOCAL",
            title="Local Position",
        )
        foreign_employee = create_employee(
            organization=self.other_organization,
            actor=self.outsider,
            employee_number="FOREIGN-POSITION",
            first_name="Foreign",
            last_name="Employee",
        )

        with self.assertRaises(PermissionDenied):
            assign_employee_position(
                organization=self.organization,
                actor=self.owner,
                employee=foreign_employee,
                position=position,
                start_date=date(2026, 9, 1),
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

    def test_employee_can_be_created_from_an_active_member_account(self) -> None:
        member = User.objects.create_user(
            username="provisioned-employee",
            first_name="Sara",
            last_name="Ahmadi",
            email="sara@example.test",
            phone_number="09120000000",
            national_id="1234567891",
            is_active=True,
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )

        employee = create_employee_from_member(
            organization=self.organization,
            actor=self.owner,
            employee_number="MEMBER-001",
            user=member,
        )

        self.assertEqual(employee.first_name, member.first_name)
        self.assertEqual(employee.last_name, member.last_name)
        self.assertEqual(employee.email, member.email)
        self.assertEqual(employee.phone_number, member.phone_number)
        self.assertEqual(employee.user, member)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(employee.pk),
                action=AuditAction.EMPLOYEE_ACCOUNT_LINKED,
            ).exists()
        )

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
            get_active_chief_executive(
                user=self.outsider,
                organization=self.organization,
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
            EmployeePositionAssignment,
            EmployeeProjectAssignment,
        ):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))


class WorkforcePanelTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="panel-workforce-owner")
        self.outsider = User.objects.create_user(username="panel-workforce-outsider")
        self.organization = Organization.objects.create(
            name="Panel Workforce Co", slug="panel-workforce-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Panel Workforce Co", slug="other-panel-workforce-co"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def _login_owner(self) -> None:
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

    def test_owner_can_open_workforce_pages_and_not_see_foreign_employee(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PANEL-LOCAL",
            first_name="Local",
            last_name="Employee",
        )
        foreign_employee = create_employee(
            organization=self.other_organization,
            actor=self.outsider,
            employee_number="PANEL-FOREIGN",
            first_name="Foreign",
            last_name="Employee",
        )
        self._login_owner()

        for name in (
            "workforce:employee_list",
            "workforce:department_list",
            "workforce:position_list",
            "workforce:work_team_list",
            "workforce:assignment_list",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse(
                    "workforce:employee_detail", kwargs={"employee_id": employee.pk}
                )
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "workforce:employee_detail",
                    kwargs={"employee_id": foreign_employee.pk},
                )
            ).status_code,
            404,
        )

    def test_position_list_links_to_tenant_scoped_position_detail(self) -> None:
        position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PANEL-POSITION",
            title="Panel Position",
        )
        foreign_position = create_position(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-POSITION",
            title="Foreign Position",
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PANEL-POSITION-001",
            first_name="Position",
            last_name="Holder",
            position=position,
        )
        self._login_owner()

        detail_url = reverse(
            "workforce:position_detail", kwargs={"position_id": position.pk}
        )
        response = self.client.get(reverse("workforce:position_list"))
        self.assertContains(response, detail_url)
        self.assertContains(self.client.get(detail_url), employee.employee_number)
        self.assertEqual(
            self.client.get(
                reverse(
                    "workforce:position_detail",
                    kwargs={"position_id": foreign_position.pk},
                )
            ).status_code,
            404,
        )

    def test_owner_can_update_position_from_its_detail_page(self) -> None:
        position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="POSITION-EDIT",
            title="Original Position",
        )
        self._login_owner()

        response = self.client.post(
            reverse("workforce:position_update", kwargs={"position_id": position.pk}),
            {
                "code": "POSITION-UPDATED",
                "title": "Updated Position",
                "department": "",
                "description": "Updated description",
                "is_single_holder": "on",
            },
        )

        position.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("workforce:position_detail", kwargs={"position_id": position.pk}),
        )
        self.assertEqual(position.code, "POSITION-UPDATED")
        self.assertEqual(position.title, "Updated Position")
        self.assertTrue(position.is_single_holder)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.POSITION_UPDATED,
                entity_id=position.pk,
            ).exists()
        )

    def test_position_parent_form_and_update_are_tenant_scoped(self) -> None:
        parent = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PARENT-FORM",
            title="Parent Form",
        )
        child = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CHILD-FORM",
            title="Child Form",
        )
        foreign_parent = create_position(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-FORM",
            title="Foreign Form",
        )
        self._login_owner()

        response = self.client.get(
            reverse("workforce:position_detail", kwargs={"position_id": child.pk})
        )
        parent_field = response.context["position_form"].fields["parent_position"]
        self.assertIn(parent, parent_field.queryset)
        self.assertNotIn(child, parent_field.queryset)
        self.assertNotIn(foreign_parent, parent_field.queryset)

        response = self.client.post(
            reverse("workforce:position_update", kwargs={"position_id": child.pk}),
            {
                "code": child.code,
                "title": child.title,
                "department": "",
                "parent_position": parent.pk,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        child.refresh_from_db()
        self.assertEqual(child.parent_position, parent)

    def test_department_chart_excludes_positions_and_is_tenant_scoped(self) -> None:
        parent = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CHART-DIRECTOR",
            title="Chart Director",
        )
        child = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CHART-ENGINEER",
            title="Chart Engineer",
            parent_position=parent,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="CHART-HOLDER",
            first_name="Chart",
            last_name="Holder",
        )
        assign_employee_position(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            position=child,
            start_date=date(2026, 9, 1),
        )
        foreign_position = create_position(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-CHART",
            title="Foreign Chart Position",
        )
        self._login_owner()

        response = self.client.get(reverse("workforce:department_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["department_tree"], [])
        self.assertNotIn("position_tree", response.context)
        self.assertNotContains(response, "Chart Director")
        self.assertNotContains(response, "Chart Engineer")
        self.assertNotContains(response, "Chart Holder")
        self.assertNotContains(response, foreign_position.title)

    def test_position_list_renders_chart_and_is_tenant_scoped(self) -> None:
        parent = create_position(
            organization=self.organization,
            actor=self.owner,
            code="POSITION-CHART-PARENT",
            title="Position Chart Parent",
        )
        child = create_position(
            organization=self.organization,
            actor=self.owner,
            code="POSITION-CHART-CHILD",
            title="Position Chart Child",
            parent_position=parent,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="POSITION-CHART-HOLDER",
            first_name="Position",
            last_name="Holder",
        )
        assign_employee_position(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            position=child,
            start_date=date(2026, 9, 1),
        )
        foreign_position = create_position(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-POSITION-CHART",
            title="Foreign Position Chart",
        )
        self._login_owner()

        response = self.client.get(reverse("workforce:position_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(reverse("workforce:position_list"), "/workforce/positions/")
        self.assertEqual(self.client.get("/workforce/chart/").status_code, 404)
        self.assertEqual(response.context["position_tree"][0]["position"], parent)
        self.assertEqual(
            response.context["position_tree"][0]["children"][0]["position"],
            child,
        )
        self.assertContains(response, "چارت سمت‌ها")
        self.assertContains(response, "Position Chart Parent")
        self.assertContains(response, "Position Chart Child")
        self.assertContains(response, "Position Holder")
        self.assertContains(response, "متصدی فعال")
        self.assertContains(response, 'aria-label="متصدی فعال: Position Holder"')
        self.assertContains(response, 'data-position-chart-view="tree"')
        self.assertContains(response, 'data-position-chart-view="list"')
        self.assertContains(response, "کد و عنوان")
        self.assertContains(response, "سمت والد")
        self.assertContains(response, "واحد شرکتی")
        self.assertContains(response, "نوع تصدی")
        self.assertContains(response, "بایگانی")
        self.assertNotContains(response, foreign_position.title)

    def test_department_list_links_to_editable_tenant_scoped_detail(self) -> None:
        department = create_department(
            organization=self.organization,
            actor=self.owner,
            code="DEPARTMENT-EDIT",
            name="Original Department",
        )
        foreign_department = create_department(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-DEPARTMENT-EDIT",
            name="Foreign Department",
        )
        self._login_owner()

        detail_url = reverse(
            "workforce:department_detail", kwargs={"department_id": department.pk}
        )
        self.assertContains(
            self.client.get(reverse("workforce:department_list")), detail_url
        )
        response = self.client.post(
            reverse(
                "workforce:department_update", kwargs={"department_id": department.pk}
            ),
            {
                "code": "DEPARTMENT-UPDATED",
                "name": "Updated Department",
                "parent": "",
                "description": "Updated description",
            },
        )

        department.refresh_from_db()
        self.assertRedirects(response, detail_url)
        self.assertEqual(department.code, "DEPARTMENT-UPDATED")
        self.assertEqual(department.name, "Updated Department")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.DEPARTMENT_UPDATED,
                entity_id=department.pk,
            ).exists()
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "workforce:department_detail",
                    kwargs={"department_id": foreign_department.pk},
                )
            ).status_code,
            404,
        )

    def test_department_page_renders_hierarchical_organization_chart(self) -> None:
        ceo_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="CEO",
            title="Chief Executive Officer",
            is_single_holder=True,
        )
        chief_executive = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="CEO-TREE-001",
            first_name="Chief",
            last_name="Executive",
            position=ceo_position,
        )
        parent = create_department(
            organization=self.organization,
            actor=self.owner,
            code="EXEC",
            name="Execution",
        )
        execution_manager = create_position(
            organization=self.organization,
            actor=self.owner,
            code="EXEC-MANAGER",
            title="Execution Manager",
            department=parent,
            is_single_holder=True,
        )
        assign_employee_position(
            organization=self.organization,
            actor=self.owner,
            employee=chief_executive,
            position=execution_manager,
            start_date=date(2026, 9, 1),
        )
        chief_executive.profile_image.name = (
            f"organizations/{self.organization.pk}/employees/{chief_executive.pk}/"
            "profile/chart-avatar.png"
        )
        chief_executive.save(update_fields=["profile_image"])
        child = create_department(
            organization=self.organization,
            actor=self.owner,
            code="SITE",
            name="Site Operations",
            parent=parent,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="TREE-001",
            first_name="Tree",
            last_name="Employee",
            department=child,
        )
        foreign_department = create_department(
            organization=self.other_organization,
            actor=self.outsider,
            code="FOREIGN-DEPARTMENT",
            name="Foreign Department",
        )
        foreign_ceo_position = create_position(
            organization=self.other_organization,
            actor=self.outsider,
            code="CEO",
            title="Foreign Chief Executive Officer",
            is_single_holder=True,
        )
        create_employee(
            organization=self.other_organization,
            actor=self.outsider,
            employee_number="FOREIGN-CEO-TREE-001",
            first_name="Foreign Chief",
            last_name="Executive",
            position=foreign_ceo_position,
        )
        create_employee(
            organization=self.other_organization,
            actor=self.outsider,
            employee_number="FOREIGN-TREE-001",
            first_name="Foreign Tree",
            last_name="Employee",
            department=foreign_department,
        )
        self._login_owner()

        response = self.client.get(reverse("workforce:department_list"))

        self.assertEqual(response.status_code, 200)
        root = response.context["department_tree"][0]
        self.assertEqual(root["department"], parent)
        self.assertEqual(root["children"][0]["department"], child)
        self.assertEqual(root["children"][0]["employees"], [employee])
        self.assertEqual(root["direct_employee_count"], 0)
        self.assertEqual(root["subtree_employee_count"], 1)
        self.assertEqual(root["theme"], "emerald")
        self.assertEqual(root["children"][0]["theme"], "amber")
        self.assertEqual(root["children"][0]["primary_employee"], employee)
        self.assertEqual(response.context["organization_employee_count"], 2)
        self.assertContains(response, self.organization.name)
        self.assertContains(response, "ریشه ساختار شرکتی")
        self.assertContains(response, "Site Operations")
        self.assertContains(response, "data-org-chart")
        self.assertContains(response, "نمای درختی")
        self.assertNotContains(response, "Execution Manager")
        self.assertNotContains(response, "Foreign Department")
        self.assertNotContains(response, "Foreign Tree")
        self.assertNotContains(response, "Foreign Chief")

    def test_employee_form_creates_from_an_existing_company_account(self) -> None:
        member = User.objects.create_user(
            username="assigned-member",
            first_name="Ali",
            last_name="Karimi",
            email="ali@example.test",
            phone_number="09121111111",
            national_id="1234567891",
            is_active=True,
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        foreign_member = User.objects.create_user(
            username="foreign-assigned-member",
            first_name="Foreign",
            last_name="Member",
        )
        self.other_organization.memberships.create(
            user=foreign_member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self._login_owner()

        response = self.client.get(reverse("workforce:employee_create"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("user", response.context["form"].fields)
        self.assertIn("source_type", response.context["form"].fields)
        self.assertNotContains(response, "جست‌وجوی کاربر")
        self.assertContains(response, member.username)
        self.assertNotContains(response, foreign_member.username)

        response = self.client.post(
            reverse("workforce:employee_create"),
            {
                "source_type": "existing_account",
                "user": str(member.pk),
                "employee_number": "EMP-INDEPENDENT-001",
                "department": "",
                "position": "",
                "work_team": "",
                "hire_date": "",
            },
        )

        employee = Employee.objects.get(
            organization=self.organization, employee_number="EMP-INDEPENDENT-001"
        )
        self.assertRedirects(
            response,
            reverse("workforce:employee_detail", kwargs={"employee_id": employee.pk}),
        )
        self.assertEqual(employee.user, member)
        self.assertEqual(employee.first_name, member.first_name)
        self.assertEqual(employee.last_name, member.last_name)
        self.assertEqual(employee.email, member.email)
        self.assertEqual(employee.phone_number, member.phone_number)

    def test_employee_form_can_create_employee_without_user_account(self) -> None:
        self._login_owner()

        response = self.client.post(
            reverse("workforce:employee_create"),
            {
                "source_type": "without_account",
                "employee_number": "EMP-MANUAL-001",
                "first_name": "Reza",
                "last_name": "Moradi",
                "email": "reza@example.test",
                "phone_number": "09122222222",
                "department": "",
                "position": "",
                "work_team": "",
                "hire_date": "",
            },
        )

        employee = Employee.objects.get(
            organization=self.organization, employee_number="EMP-MANUAL-001"
        )
        self.assertRedirects(
            response,
            reverse("workforce:employee_detail", kwargs={"employee_id": employee.pk}),
        )
        self.assertIsNone(employee.user)
        self.assertEqual(employee.first_name, "Reza")
        self.assertEqual(employee.last_name, "Moradi")

    def test_employee_account_card_reveals_selector_on_demand(self) -> None:
        member = User.objects.create_user(
            username="account-card-member",
            first_name="Mina",
            last_name="Rahimi",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="ACCOUNT-CARD-001",
            first_name="Mina",
            last_name="Rahimi",
        )
        self._login_owner()

        detail_url = reverse(
            "workforce:employee_detail", kwargs={"employee_id": employee.pk}
        )
        response = self.client.get(detail_url)

        self.assertContains(response, "حساب کاربری متصل نشده است.")
        self.assertContains(response, "data-account-link-panel")
        self.assertContains(response, "اتصال حساب کاربری")

        response = self.client.post(
            reverse(
                "workforce:employee_account_link",
                kwargs={"employee_id": employee.pk},
            ),
            {"user": str(member.pk)},
        )

        employee.refresh_from_db()
        self.assertRedirects(response, detail_url)
        self.assertEqual(employee.user, member)
        response = self.client.get(detail_url)
        self.assertContains(response, f"@{member.username}")
        self.assertContains(response, "حساب متصل")
        self.assertContains(response, "قطع اتصال حساب")
        self.assertNotContains(response, "data-account-link-panel")

    def test_owner_can_upload_and_privately_view_employee_profile_image(self) -> None:
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PANEL-PROFILE-001",
            first_name="Profile",
            last_name="Employee",
        )
        foreign_employee = create_employee(
            organization=self.other_organization,
            actor=self.outsider,
            employee_number="FOREIGN-PROFILE-001",
            first_name="Foreign",
            last_name="Profile",
        )
        self._login_owner()

        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            response = self.client.post(
                reverse(
                    "workforce:employee_profile_image_update",
                    kwargs={"employee_id": employee.pk},
                ),
                {
                    "profile_image": SimpleUploadedFile(
                        "employee.png",
                        b"\x89PNG\r\n\x1a\n" + b"private-employee-profile",
                        content_type="image/png",
                    )
                },
            )

            employee.refresh_from_db()
            detail_url = reverse(
                "workforce:employee_detail", kwargs={"employee_id": employee.pk}
            )
            self.assertRedirects(response, detail_url)
            detail = self.client.get(detail_url)
            image_url = reverse(
                "workforce:employee_profile_image",
                kwargs={"employee_id": employee.pk},
            )
            self.assertContains(detail, image_url)
            self.assertNotContains(detail, employee.profile_image.name)
            image_response = self.client.get(image_url)
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response["Content-Type"], "image/png")
            self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(
                self.client.get(
                    reverse(
                        "workforce:employee_profile_image",
                        kwargs={"employee_id": foreign_employee.pk},
                    )
                ).status_code,
                404,
            )

    def test_employee_form_filters_positions_by_selected_department(self) -> None:
        first_department = create_department(
            organization=self.organization,
            actor=self.owner,
            code="FIRST",
            name="First Department",
        )
        second_department = create_department(
            organization=self.organization,
            actor=self.owner,
            code="SECOND",
            name="Second Department",
        )
        first_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="FIRST-POS",
            title="First Position",
            department=first_department,
        )
        second_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="SECOND-POS",
            title="Second Position",
            department=second_department,
        )
        self._login_owner()

        response = self.client.get(
            reverse("workforce:employee_positions"),
            {"department": str(first_department.pk)},
        )

        self.assertContains(response, first_position.title)
        self.assertNotContains(response, second_position.title)

        response = self.client.post(
            reverse("workforce:employee_create"),
            {
                "source_type": "without_account",
                "employee_number": "EMP-WRONG-POSITION",
                "first_name": "Wrong",
                "last_name": "Position",
                "department": str(first_department.pk),
                "position": str(second_position.pk),
                "work_team": "",
                "hire_date": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Employee.objects.filter(
                organization=self.organization,
                employee_number="EMP-WRONG-POSITION",
            ).exists()
        )

    def test_employee_detail_can_add_and_end_a_second_position(self) -> None:
        first_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PANEL-FIRST",
            title="Panel First Position",
        )
        second_position = create_position(
            organization=self.organization,
            actor=self.owner,
            code="PANEL-SECOND",
            title="Panel Second Position",
        )
        employee = create_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="PANEL-MULTI-001",
            first_name="Panel",
            last_name="Multiple",
            position=first_position,
        )
        self._login_owner()

        response = self.client.post(
            reverse(
                "workforce:employee_position_assign",
                kwargs={"employee_id": employee.pk},
            ),
            {
                "position": str(second_position.pk),
                "start_date": "2026-09-02",
                "is_primary": "",
                "notes": "Secondary duty",
            },
        )

        assignment = employee.position_assignments.get(position=second_position)
        self.assertRedirects(
            response,
            reverse("workforce:employee_detail", kwargs={"employee_id": employee.pk}),
        )
        detail = self.client.get(
            reverse("workforce:employee_detail", kwargs={"employee_id": employee.pk})
        )
        self.assertContains(detail, first_position.title)
        self.assertContains(detail, second_position.title)

        response = self.client.post(
            reverse(
                "workforce:employee_position_end",
                kwargs={
                    "employee_id": employee.pk,
                    "assignment_id": assignment.pk,
                },
            ),
            {"end_date": "2026-09-03"},
        )

        assignment.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("workforce:employee_detail", kwargs={"employee_id": employee.pk}),
        )
        self.assertEqual(assignment.status, PositionAssignmentStatus.ENDED)


class SeedWorkforceCommandTests(TestCase):
    def test_profile_image_population_reaches_rounded_eighty_percent(self) -> None:
        with (
            tempfile.TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            call_command("seed_workforce", stdout=StringIO())
            call_command(
                "populate_employee_profile_images",
                percentage=80,
                stdout=StringIO(),
            )

            self.assertEqual(Employee.objects.count(), 5)
            self.assertEqual(Employee.objects.exclude(profile_image="").count(), 4)
            call_command(
                "populate_employee_profile_images",
                percentage=80,
                stdout=StringIO(),
            )
            self.assertEqual(Employee.objects.exclude(profile_image="").count(), 4)

    def test_seed_workforce_is_idempotent_and_preserves_tenant_scope(self) -> None:
        call_command("seed_workforce", stdout=StringIO())

        organization = Organization.objects.get(slug="seed-workforce-demo")
        self.assertEqual(
            Department.objects.filter(organization=organization).count(), 3
        )
        self.assertEqual(Position.objects.filter(organization=organization).count(), 4)
        self.assertEqual(WorkTeam.objects.filter(organization=organization).count(), 2)
        self.assertEqual(Employee.objects.filter(organization=organization).count(), 5)
        self.assertEqual(
            EmployeePositionAssignment.objects.filter(
                organization=organization,
                status=PositionAssignmentStatus.ACTIVE,
                is_primary=True,
            ).count(),
            5,
        )
        self.assertEqual(
            set(
                Employee.objects.filter(organization=organization).values_list(
                    "status", flat=True
                )
            ),
            {EmployeeStatus.ACTIVE, EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED},
        )
        self.assertEqual(
            set(
                EmployeeProjectAssignment.objects.filter(
                    organization=organization
                ).values_list("status", flat=True)
            ),
            {
                AssignmentStatus.ACTIVE,
                AssignmentStatus.COMPLETED,
                AssignmentStatus.CANCELLED,
            },
        )

        call_command("seed_workforce", stdout=StringIO())
        self.assertEqual(
            Department.objects.filter(organization=organization).count(), 3
        )
        self.assertEqual(Position.objects.filter(organization=organization).count(), 4)
        self.assertEqual(WorkTeam.objects.filter(organization=organization).count(), 2)
        self.assertEqual(Employee.objects.filter(organization=organization).count(), 5)
        self.assertEqual(
            EmployeeProjectAssignment.objects.filter(organization=organization).count(),
            3,
        )
