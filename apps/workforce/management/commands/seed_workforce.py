"""Create an idempotent Persian workforce demonstration dataset."""

import sys
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project, ProjectSite, ProjectStatus
from apps.projects.services import create_project, create_project_site
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
    assign_employee_to_project,
    create_department,
    create_employee,
    create_position,
    create_work_team,
    transition_employee_status,
    transition_project_assignment_status,
)


class Command(BaseCommand):
    help = "Create deterministic Persian workforce demo data in development only."

    organization_slug = "seed-workforce-demo"
    project_code = "WF-SEED-01"
    site_code = "MAIN"

    def handle(self, *args: object, **options: object) -> None:
        if not settings.DEBUG and "pytest" not in sys.modules:
            raise CommandError(
                "seed_workforce is restricted to config.settings.development with DEBUG=True."
            )

        before = self._counts()
        with transaction.atomic():
            owner = self._get_owner()
            organization = self._get_organization(owner)
            project, site = self._get_project_and_site(organization, owner)
            self._seed_workforce(organization, owner, project, site)

        after = self._counts()
        self.stdout.write(self.style.SUCCESS("Persian workforce demo data is ready."))
        for label, count in after.items():
            self.stdout.write(f"{label}: {count - before[label]} created")

    def _counts(self) -> dict[str, int]:
        return {
            "departments": Department.objects.count(),
            "positions": Position.objects.count(),
            "work teams": WorkTeam.objects.count(),
            "employees": Employee.objects.count(),
            "project assignments": EmployeeProjectAssignment.objects.count(),
        }

    def _get_owner(self) -> User:
        owner, created = User.objects.get_or_create(
            username="seed.workforce.owner",
            defaults={
                "first_name": "سارا",
                "last_name": "موسوی",
                "email": "seed.workforce.owner@example.test",
            },
        )
        if created:
            owner.set_unusable_password()
            owner.save(update_fields=["password"])
        return owner

    def _get_organization(self, owner: User) -> Organization:
        organization = Organization.objects.filter(slug=self.organization_slug).first()
        if organization is not None:
            return organization
        return create_organization_with_owner(
            owner=owner,
            name="شرکت نمونه نیروی سازه",
            legal_name="شرکت نمونه نیروی سازه (سهامی خاص)",
            slug=self.organization_slug,
            timezone_name="Asia/Tehran",
            currency="IRR",
        )

    def _get_project_and_site(
        self, organization: Organization, owner: User
    ) -> tuple[Project, ProjectSite]:
        project = Project.objects.filter(
            organization=organization, code=self.project_code
        ).first()
        if project is None:
            project = create_project(
                organization=organization,
                actor=owner,
                code=self.project_code,
                name="مجتمع مسکونی سروستان",
                description="پروژه نمونه برای تخصیص و مدیریت نیروی انسانی کارگاه.",
                status=ProjectStatus.ACTIVE,
                start_date=date(2026, 3, 21),
            )
        site = ProjectSite.objects.filter(
            organization=organization, project=project, code=self.site_code
        ).first()
        if site is None:
            site = create_project_site(
                organization=organization,
                project=project,
                actor=owner,
                code=self.site_code,
                name="کارگاه اصلی سروستان",
                address="تهران، منطقه ۲۲، بلوار پژوهش",
            )
        return project, site

    def _seed_workforce(
        self,
        organization: Organization,
        owner: User,
        project: Project,
        site: ProjectSite,
    ) -> None:
        departments = self._departments(organization, owner)
        positions = self._positions(organization, owner, departments)

        leaders = {
            "civil": self._employee(
                organization,
                owner,
                "WF-001",
                "رضا",
                "صادقی",
                department=departments["execution"],
                position=positions["site_manager"],
                email="reza.sadeghi@example.test",
                phone_number="۰۹۱۲۱۲۳۴۵۶۷",
                hire_date=date(2021, 7, 10),
            ),
            "installations": self._employee(
                organization,
                owner,
                "WF-002",
                "مینا",
                "کریمی",
                department=departments["technical"],
                position=positions["mechanical_engineer"],
                email="mina.karimi@example.test",
                phone_number="۰۹۱۲۲۳۴۵۶۷۸",
                hire_date=date(2022, 2, 1),
            ),
        }
        teams = self._teams(organization, owner, departments, leaders)
        employees = {
            **leaders,
            "foreman": self._employee(
                organization,
                owner,
                "WF-003",
                "حامد",
                "حسینی",
                department=departments["execution"],
                position=positions["foreman"],
                work_team=teams["civil"],
                email="hamed.hosseini@example.test",
                phone_number="۰۹۱۲۳۴۵۶۷۸۹",
                hire_date=date(2023, 5, 15),
            ),
            "electrician": self._employee(
                organization,
                owner,
                "WF-004",
                "لیلا",
                "احمدی",
                department=departments["technical"],
                position=positions["electrician"],
                work_team=teams["installations"],
                email="leila.ahmadi@example.test",
                phone_number="۰۹۱۲۳۴۵۶۷۹۰",
                hire_date=date(2024, 1, 20),
            ),
            "former_worker": self._employee(
                organization,
                owner,
                "WF-005",
                "مجتبی",
                "مرادی",
                department=departments["execution"],
                position=positions["foreman"],
                work_team=teams["civil"],
                email="mojtaba.moradi@example.test",
                phone_number="۰۹۱۲۳۴۵۶۷۹۱",
                hire_date=date(2023, 8, 1),
            ),
        }

        self._active_assignment(
            organization, owner, employees["foreman"], project, site
        )
        self._closed_assignment(
            organization,
            owner,
            employees["electrician"],
            project,
            site,
            AssignmentStatus.COMPLETED,
            date(2026, 6, 30),
        )
        self._closed_assignment(
            organization,
            owner,
            employees["former_worker"],
            project,
            None,
            AssignmentStatus.CANCELLED,
            date(2026, 5, 20),
        )
        self._ensure_employee_status(
            organization, owner, employees["electrician"], EmployeeStatus.INACTIVE
        )
        self._ensure_employee_status(
            organization,
            owner,
            employees["former_worker"],
            EmployeeStatus.TERMINATED,
            effective_date=date(2026, 5, 21),
        )

    def _departments(
        self, organization: Organization, owner: User
    ) -> dict[str, Department]:
        data = (
            (
                "technical",
                "TEC",
                "دفتر فنی و مهندسی",
                "کنترل نقشه‌ها و هماهنگی فنی پروژه",
            ),
            (
                "execution",
                "EXE",
                "اجرای پروژه",
                "مدیریت عملیات اجرایی و اکیپ‌های کارگاهی",
            ),
            ("support", "SUP", "پشتیبانی کارگاه", "تدارکات، ایمنی و امور پشتیبانی"),
        )
        return {
            key: self._department(organization, owner, code, name, description)
            for key, code, name, description in data
        }

    def _department(
        self,
        organization: Organization,
        owner: User,
        code: str,
        name: str,
        description: str,
    ) -> Department:
        department = Department.objects.filter(
            organization=organization, code=code
        ).first()
        return department or create_department(
            organization=organization,
            actor=owner,
            code=code,
            name=name,
            description=description,
        )

    def _positions(
        self,
        organization: Organization,
        owner: User,
        departments: dict[str, Department],
    ) -> dict[str, Position]:
        data = (
            ("site_manager", "SITE-MGR", "مدیر کارگاه", "execution"),
            ("foreman", "FOREMAN", "سرپرست اجرایی", "execution"),
            ("mechanical_engineer", "MECH-ENG", "مهندس تأسیسات مکانیکی", "technical"),
            ("electrician", "ELEC-TECH", "تکنسین برق", "technical"),
        )
        result = {}
        for key, code, title, department_key in data:
            position = Position.objects.filter(
                organization=organization, code=code
            ).first()
            result[key] = position or create_position(
                organization=organization,
                actor=owner,
                code=code,
                title=title,
                department=departments[department_key],
                description=f"سمت {title} در ساختار نمونه.",
            )
        return result

    def _teams(
        self,
        organization: Organization,
        owner: User,
        departments: dict[str, Department],
        leaders: dict[str, Employee],
    ) -> dict[str, WorkTeam]:
        data = (
            ("civil", "CIVIL", "اکیپ اجرای سازه", "execution", "civil"),
            ("installations", "MEP", "اکیپ تأسیسات", "technical", "installations"),
        )
        result = {}
        for key, code, name, department_key, leader_key in data:
            team = WorkTeam.objects.filter(organization=organization, code=code).first()
            result[key] = team or create_work_team(
                organization=organization,
                actor=owner,
                code=code,
                name=name,
                department=departments[department_key],
                lead=leaders[leader_key],
                description=f"{name} برای پروژه نمونه سروستان.",
            )
        return result

    def _employee(
        self,
        organization: Organization,
        owner: User,
        employee_number: str,
        first_name: str,
        last_name: str,
        **kwargs: object,
    ) -> Employee:
        employee = Employee.objects.filter(
            organization=organization, employee_number=employee_number
        ).first()
        return employee or create_employee(
            organization=organization,
            actor=owner,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            **kwargs,
        )

    def _active_assignment(
        self,
        organization: Organization,
        owner: User,
        employee: Employee,
        project: Project,
        site: ProjectSite,
    ) -> None:
        if not EmployeeProjectAssignment.objects.filter(
            employee=employee, project=project, site=site
        ).exists():
            assign_employee_to_project(
                organization=organization,
                actor=owner,
                employee=employee,
                project=project,
                site=site,
                start_date=date(2026, 7, 1),
                role_title="سرپرست آرماتوربندی",
                notes="مسئول هماهنگی اکیپ سازه در جبهه جنوبی کارگاه.",
            )

    def _closed_assignment(
        self,
        organization: Organization,
        owner: User,
        employee: Employee,
        project: Project,
        site: ProjectSite | None,
        status: str,
        end_date: date,
    ) -> None:
        assignment = EmployeeProjectAssignment.objects.filter(
            employee=employee, project=project, site=site
        ).first()
        if assignment is None:
            assignment = assign_employee_to_project(
                organization=organization,
                actor=owner,
                employee=employee,
                project=project,
                site=site,
                start_date=date(2026, 4, 1),
                role_title="نیروی اجرایی",
                notes="تخصیص نمونه برای نمایش سابقه نیروی انسانی.",
            )
        if assignment.status == AssignmentStatus.ACTIVE:
            transition_project_assignment_status(
                organization=organization,
                actor=owner,
                assignment=assignment,
                target_status=status,
                end_date=end_date,
            )

    def _ensure_employee_status(
        self,
        organization: Organization,
        owner: User,
        employee: Employee,
        status: str,
        effective_date: date | None = None,
    ) -> None:
        if employee.status == EmployeeStatus.ACTIVE:
            transition_employee_status(
                organization=organization,
                actor=owner,
                employee=employee,
                target_status=status,
                effective_date=effective_date,
            )
