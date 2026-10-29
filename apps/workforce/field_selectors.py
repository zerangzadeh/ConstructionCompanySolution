"""Read-only operational projections and validated journey context."""

from dataclasses import dataclass
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.projects.models import Project, ProjectSite

from .models import Employee, EmployeeProjectAssignment, WorkRelationship


@dataclass(frozen=True)
class FieldContext:
    project: Project | None = None
    site: ProjectSite | None = None
    employee: Employee | None = None

    @property
    def query(self) -> str:
        return urlencode(
            {
                key: str(value.pk)
                for key, value in (
                    ("project", self.project),
                    ("site", self.site),
                    ("employee", self.employee),
                )
                if value is not None
            }
        )


def scoped_employees(*, organization, user, assigned_only=False) -> QuerySet[Employee]:
    membership = get_active_membership(user=user, organization=organization)
    assignments = scope_queryset(
        EmployeeProjectAssignment.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    # An organization grant keeps the existing unassigned-worker behavior.
    from apps.organizations.authorization import membership_has_scope

    employees = Employee.objects.filter(organization=organization, archived_at=None)
    if assigned_only or not membership_has_scope(membership):
        employees = employees.filter(pk__in=assignments.values("employee_id"))
    return employees


def resolve_field_context(
    *, organization, user, values, include_employee=False
) -> FieldContext:
    membership = get_active_membership(user=user, organization=organization)
    projects = scope_queryset(
        Project.objects.filter(organization=organization, deleted_at=None),
        membership=membership,
        project_lookup="pk",
        include_site_parent=True,
    )
    sites = scope_queryset(
        ProjectSite.objects.filter(organization=organization).select_related("project"),
        membership=membership,
        project_lookup="project_id",
        site_lookup="pk",
    )
    try:
        project = (
            get_object_or_404(projects, pk=values["project"])
            if values.get("project")
            else None
        )
        site = (
            get_object_or_404(sites, pk=values["site"]) if values.get("site") else None
        )
        if site and project and site.project_id != project.pk:
            raise Http404
        if site and not project:
            project = get_object_or_404(projects, pk=site.project_id)
        context = FieldContext(project=project, site=site)
        employee = None
        if include_employee and values.get("employee"):
            employee = get_object_or_404(
                context_employees(
                    scoped_employees(organization=organization, user=user), context
                ),
                pk=values["employee"],
            )
        return FieldContext(project=project, site=site, employee=employee)
    except (ValidationError, ValueError, TypeError) as exc:
        raise Http404 from exc


def context_employees(
    employees: QuerySet[Employee], context: FieldContext
) -> QuerySet[Employee]:
    assignments = EmployeeProjectAssignment.objects.filter(
        organization_id=employees.values("organization_id")[:1]
    )
    if context.project:
        assignments = assignments.filter(project=context.project)
    if context.site:
        assignments = assignments.filter(site=context.site)
    if context.project or context.site:
        employees = employees.filter(pk__in=assignments.values("employee_id"))
    return employees


def field_employees(*, organization, user, context: FieldContext) -> QuerySet[Employee]:
    employees = context_employees(
        scoped_employees(organization=organization, user=user), context
    )
    relationships = WorkRelationship.objects.filter(
        organization=organization
    ).select_related("person")
    return employees.select_related("position", "work_team").prefetch_related(
        Prefetch(
            "work_relationships", queryset=relationships, to_attr="field_relationships"
        )
    )


def employee_person(employee: Employee):
    relations = getattr(employee, "field_relationships", None)
    if relations is None:
        relations = list(employee.work_relationships.select_related("person"))
    people = {relation.person_id: relation.person for relation in relations}
    if len(people) > 1:
        raise ValidationError("هویت نیروی کار نیازمند بررسی مسئول مجاز است.")
    return next(iter(people.values()), None)


def current_assignments(*, organization, user, employee=None, context=None):
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    records = scope_queryset(
        EmployeeProjectAssignment.objects.filter(
            organization=organization, status="active", start_date__lte=today
        ).filter(Q(end_date=None) | Q(end_date__gte=today)),
        membership=get_active_membership(user=user, organization=organization),
        project_lookup="project_id",
        site_lookup="site_id",
    )
    if employee:
        records = records.filter(employee=employee)
    if context and context.project:
        records = records.filter(project=context.project)
    if context and context.site:
        records = records.filter(site=context.site)
    return records.select_related("project", "site")
