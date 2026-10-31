"""Read-only project context for the dedicated commercial workspaces."""

from dataclasses import dataclass

from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest
from django.urls import reverse

from apps.billing.services import get_progress_claims
from apps.contracts.services import get_organization_contracts
from apps.estimates.services import get_organization_estimates
from apps.organizations.authorization import has_business_permission
from apps.organizations.form_scoping import normalized_uuid
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.models import Project
from apps.projects.services import get_organization_project
from core.business_choices import contextual_url
from core.product_surface import route_exposed


@dataclass(frozen=True)
class CommercialSummary:
    label: str
    total: int
    state_count: int
    state_label: str
    list_url: str
    list_label: str = ""
    recent_label: str = ""
    recent_status: str = ""
    recent_url: str = ""
    create_url: str = ""
    create_label: str = ""


def project_commercial_summary(
    request: HttpRequest, project: Project
) -> tuple[CommercialSummary, ...]:
    """Project is already authorized; each source retains its own read scope."""
    cards = []
    for (
        label,
        permission,
        loader,
        namespace,
        state,
        state_label,
        create_permission,
        create_label,
    ) in (
        (
            "برآوردها",
            P.ESTIMATES_VIEW,
            get_organization_estimates,
            "estimates",
            "draft",
            "پیش‌نویس",
            P.ESTIMATES_CREATE,
            "برآورد جدید",
        ),
        (
            "قراردادها",
            P.CONTRACTS_VIEW,
            get_organization_contracts,
            "contracts",
            "active",
            "فعال",
            P.CONTRACTS_CREATE,
            "قرارداد جدید",
        ),
        (
            "صورت‌وضعیت‌ها",
            P.CLAIMS_VIEW,
            get_progress_claims,
            "billing",
            "submitted",
            "در انتظار بررسی",
            None,
            "",
        ),
    ):
        list_route = (
            "billing:claim_list" if namespace == "billing" else f"{namespace}:list"
        )
        if not route_exposed(list_route) or not has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=project,
        ):
            continue
        kwargs = {"actor" if namespace == "billing" else "user": request.user}
        records = loader(organization=request.organization, **kwargs).filter(
            project=project
        )
        counts = records.aggregate(
            total=Count("pk"), state_count=Count("pk", filter=Q(status=state))
        )
        recent = records.order_by("-created_at", "pk").first()
        create_url = ""
        if (
            create_permission
            and route_exposed(f"{namespace}:create")
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=create_permission,
                project=project,
            )
        ):
            create_url = contextual_url(
                f"{namespace}:create",
                **{"project_id" if namespace == "estimates" else "project": project.pk},
            )
        if recent and namespace == "billing":
            recent_label = (
                f"صورت‌وضعیت {recent.claim_number} · نسخه {recent.revision_number}"
            )
            detail_route = "billing:claim_detail"
        else:
            recent_label = recent.title if recent else ""
            detail_route = f"{namespace}:detail"
        cards.append(
            CommercialSummary(
                label=label,
                **counts,
                state_label=state_label,
                list_url=contextual_url(list_route, project_id=project.pk),
                list_label={
                    "estimates": "مشاهده همه برآوردهای پروژه",
                    "contracts": "مشاهده همه قراردادهای پروژه",
                    "billing": "مشاهده همه صورت‌وضعیت‌های پروژه",
                }[namespace],
                recent_label=recent_label,
                recent_status=recent.get_status_display() if recent else "",
                recent_url=(
                    reverse(detail_route, args=[recent.pk])
                    + (f"?project_id={project.pk}" if namespace == "estimates" else "")
                )
                if recent
                else "",
                create_url=create_url,
                create_label=create_label,
            )
        )
    return tuple(cards)


def filter_project_context(
    request: HttpRequest, records: QuerySet
) -> tuple[QuerySet, Project | None]:
    """A local filter intersects source scope; it never changes session context."""
    value = request.GET.get("project_id", "").strip()
    if not value:
        return records, None
    project_id = normalized_uuid(value)
    if project_id is None:
        raise Http404
    project = get_organization_project(
        user=request.user, organization=request.organization, project_id=project_id
    )
    return records.filter(project=project), project
