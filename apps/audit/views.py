from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.audit.forms import AuditFilterForm
from apps.audit.models import AuditAction
from apps.audit.services import get_organization_audit_events
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import build_filter_bar, paginate_table, table_pagination_query

_PAGE_SIZES = (10, 20, 25, 50, 100)
_DEFAULT_PAGE_SIZE = 25
_SORT_FIELDS = {"date": ("created_at", "pk"), "actor": ("actor__username", "pk")}


@active_organization_required
@organization_permission_required(BusinessPermissionCode.AUDIT_VIEW)
@require_GET
def audit_log(request: HttpRequest) -> HttpResponse:
    """Display audit events for the authenticated user's active organization."""

    events = get_organization_audit_events(
        user=request.user,
        organization=request.organization,
    )
    organization = request.organization
    settings_record = getattr(organization, "settings", None)
    audit_timezone = ZoneInfo(
        settings_record.timezone if settings_record else organization.timezone
    )
    form = AuditFilterForm(request.GET)
    if form.is_valid():
        filters = form.cleaned_data
        if term := filters["q"]:
            title_query = term.casefold()
            matching_actions = [
                value
                for value, label in AuditAction.choices
                if title_query in label.casefold()
            ]
            events = events.filter(
                Q(action__in=matching_actions) | Q(actor__username__icontains=term)
            )
        if actor := filters["actor"]:
            events = events.filter(actor__username__iexact=actor)
        if action := filters["action"]:
            events = events.filter(action=action)
        if start := filters["date_from"]:
            events = events.filter(
                created_at__gte=datetime.combine(start, time.min, audit_timezone)
            )
        if (end := filters["date_to"]) and end < date.max:
            next_day = datetime.combine(
                end + timedelta(days=1), time.min, audit_timezone
            )
            events = events.filter(created_at__lt=next_day)
    else:
        events = events.none()

    page_sizes = {str(size): size for size in _PAGE_SIZES}
    per_page = page_sizes.get(request.GET.get("per_page"), _DEFAULT_PAGE_SIZE)
    page = paginate_table(
        events,
        request,
        sort_fields=_SORT_FIELDS,
        default_ordering=("-created_at", "-pk"),
        per_page=per_page,
    )
    filter_bar = build_filter_bar(
        request,
        form=form,
        quick_fields=("actor", "action"),
        secondary_fields=("date_from", "date_to"),
        context={"per_page": str(per_page)} if per_page != _DEFAULT_PAGE_SIZE else {},
        result_count=page.paginator.count,
        result_label="رویداد",
    )
    return render(
        request,
        "audit/log.html",
        {
            "events": page.object_list,
            "page_obj": page,
            "pagination_rendered": True,
            "pagination_query": table_pagination_query(request),
            "page_size_options": _PAGE_SIZES,
            "page_size_state": {
                name: value
                for name in (*form.fields, "sort", "direction")
                if (value := request.GET.get(name))
            },
            "filter_bar": filter_bar,
            "audit_timezone": audit_timezone,
            "sort_key": request.GET.get("sort"),
            "sort_direction": (
                "descending"
                if request.GET.get("direction", "").strip().lower() == "desc"
                else "ascending"
            ),
        },
    )
