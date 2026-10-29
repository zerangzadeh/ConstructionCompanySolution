from django import template
from django.urls import reverse

from apps.organizations.authorization import has_business_permission
from apps.workforce.field_selectors import FieldContext
from core.product_surface import NAVIGATION_GROUPS, route_exposed, surface_profile

register = template.Library()


@register.inclusion_tag("workforce/_journey_links.html", takes_context=True)
def field_journey(context, project, site=None):
    request = context["request"]
    links = []
    for route, permission, label in (
        ("workforce:field_list", "employees.view", "نیروهای کار"),
        ("timekeeping:workbench", "attendance.view", "حضور و کارکرد"),
    ):
        if route_exposed(route) and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=project,
            site=site,
            allow_site_parent=True,
        ):
            query = FieldContext(project=project, site=site).query
            links.append({"label": label, "url": f"{reverse(route)}?{query}"})
    return {"links": links}


@register.simple_tag(takes_context=True)
def prepare_native_choices(context, form):
    """Opt-in native fallback; evaluate only the form's already scoped querysets."""
    from apps.workforce.field_forms import SearchChoiceSelect

    request = context["request"]
    if request.GET.get("native_choices") == "1":
        for field in form.fields.values():
            if isinstance(field.widget, SearchChoiceSelect):
                field.empty_label = f"انتخاب {field.label}"
                field.widget.choices = field.choices
    if request.POST.get("_refresh_choices") == "1":
        from django.forms.utils import ErrorDict

        form._errors = ErrorDict()
    return ""


@register.simple_tag(takes_context=True)
def native_choices_url(context):
    request = context["request"]
    query = request.GET.copy()
    query["native_choices"] = "1"
    return f"{request.path}?{query.urlencode()}"


@register.simple_tag
def has_business_choices(form):
    from apps.workforce.field_forms import SearchChoiceSelect

    return any(
        isinstance(field.widget, SearchChoiceSelect) for field in form.fields.values()
    )


@register.simple_tag
def workforce_mvp():
    return surface_profile() == "MVP"


def _validated_navigation_context(context):
    field_context = context.get("field_context")
    project = getattr(field_context, "project", None)
    site = getattr(field_context, "site", None)
    if field_context is None:
        # Filters have already been validated by the view. Do not copy raw URL IDs.
        form = context.get("form")
        if form is not None and not form.errors:
            project = getattr(form, "cleaned_data", {}).get("project")
            site = getattr(form, "cleaned_data", {}).get("site")
    return FieldContext(project=project, site=site)


@register.simple_tag(takes_context=True)
def field_context_url(context, route):
    query = _validated_navigation_context(context).query
    url = reverse(route)
    return f"{url}?{query}" if query else url


@register.simple_tag(takes_context=True)
def field_breadcrumbs(
    context, current_label, workforce_parent=False, assignment_parent=False,
    team_parent=False,
):
    operations = next(group for group in NAVIGATION_GROUPS if group.key == "operations")
    visible_operations = next(
        (
            group
            for group in context.get("product_navigation_groups", ())
            if group.key == operations.key
        ),
        None,
    )
    home = reverse("home")
    crumbs = [
        {"label": "خانه", "url": home},
        {
            "label": operations.label,
            "url": f"{home}#home-{operations.key}" if visible_operations else None,
        },
    ]
    if workforce_parent or assignment_parent or team_parent:
        master = next(
            link for link in operations.links if link.route == "workforce:field_list"
        )
        available = visible_operations and any(
            link.route == master.route for link in visible_operations.links
        )
        crumbs.append(
            {
                "label": master.label,
                "url": field_context_url(context, master.route) if available else None,
            }
        )
    if assignment_parent:
        request = context["request"]
        route = "workforce:assignment_list"
        available = route_exposed(route) and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission="project_assignments.view",
            allow_any_scope=True,
        )
        crumbs.append(
            {
                "label": "تخصیص نیرو به پروژه و کارگاه",
                "url": field_context_url(context, route) if available else None,
            }
        )
    if team_parent:
        request = context["request"]
        route = "workforce:work_team_list"
        available = route_exposed(route) and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission="work_teams.view",
            allow_any_scope=True,
        )
        crumbs.append(
            {"label": "گروه‌های کاری", "url": reverse(route) if available else None}
        )
    crumbs.append({"label": current_label})
    return crumbs


@register.inclusion_tag("workforce/_field_navigation.html", takes_context=True)
def field_navigation(context):
    """One permission-aware internal navigation for the Workforce experience."""
    request = context["request"]
    current = request.resolver_match.url_name
    query = _validated_navigation_context(context).query
    links = []
    for route, permission, label, names in (
        (
            "workforce:field_list",
            "employees.view",
            "نیروها",
            (
                "field_list",
                "field_detail",
                "field_edit",
                "field_create",
                "employee_list",
                "employee_create",
                "employee_detail",
            ),
        ),
        (
            "workforce:assignment_list",
            "project_assignments.view",
            "تخصیص به پروژه و کارگاه",
            ("assignment_list", "assignment_create", "field_assign"),
        ),
        (
            "workforce:work_team_list",
            "work_teams.view",
            "گروه‌های کاری",
            ("work_team_list", "work_team_create"),
        ),
    ):
        if route_exposed(route) and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            allow_any_scope=True,
        ):
            url = reverse(route)
            if query and route != "workforce:work_team_list":
                url += f"?{query}"
            links.append({"url": url, "label": label, "active": current in names})
    return {"links": links}
