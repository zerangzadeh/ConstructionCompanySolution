"""Discover only records exposed by the existing source workspaces."""

from django.core.exceptions import PermissionDenied

from apps.organizations.authorization import require_business_permission, scope_queryset

from .services import _source_registry

SOURCE_LABELS = {
    "field_observation": "مشاهده میدانی",
    "inspection": "بازرسی",
    "inspection_finding": "یافته بازرسی",
    "nonconformance": "عدم انطباق",
    "capa_action": "اقدام اصلاحی",
    "partner_evaluation": "ارزیابی همکار",
    "support_case": "مورد پشتیبانی",
}


def visible_references(*, organization, actor, sources=True):
    from apps.compliance.services import scoped_inspections
    from apps.daily_reports.field_services import list_field_observations

    groups, references = [], {}
    for kind, (
        model,
        final_states,
        version_attr,
        permission,
    ) in _source_registry().items():
        try:
            if kind == "field_observation":
                queryset = list_field_observations(
                    organization=organization, actor=actor
                )
                label = lambda item: item.title
            elif kind == "inspection":
                queryset = scoped_inspections(organization=organization, actor=actor)
                label = lambda item: f"{item.number} — {item.title}"
            else:
                membership = require_business_permission(
                    user=actor,
                    organization=organization,
                    permission=permission,
                    message="اجازه مشاهده فهرست این منبع را ندارید.",
                )
                queryset = model.objects.filter(organization=organization)
                if kind == "support_case":
                    queryset = queryset.filter(requester=actor)
                    label = lambda item: item.summary
                else:
                    queryset = scope_queryset(
                        queryset,
                        membership=membership,
                        project_lookup="project_id",
                        site_lookup="site_id",
                    )
                    # These source workspaces already use the business number as identity.
                    if kind == "partner_evaluation":
                        # Same permission/query/scope as scoped_evaluations. That
                        # existing helper omits require_business_permission's
                        # mandatory message; keep its unrelated implementation intact.
                        queryset = queryset.select_related("profile__party", "project")
                        label = lambda item: (
                            f"{item.profile.party} — {item.project} — {item.get_status_display()}"
                        )
                    else:
                        label = lambda item: item.number
            if sources:
                queryset = queryset.filter(status__in=final_states)
            choices = []
            for item in queryset[:50]:
                version = str(getattr(item, version_attr))
                key = f"{kind}:{item.pk}:{version}"
                references[key] = {"type": kind, "id": item.pk, "version": version}
                choices.append((key, label(item)))
            if choices:
                groups.append((SOURCE_LABELS[kind], choices))
        except PermissionDenied:
            continue
    return groups, references
