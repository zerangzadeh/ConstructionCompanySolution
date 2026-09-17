from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import (
    Case,
    Exists,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Value,
    When,
)
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import (
    Position,
    PositionAssignmentStatus,
)

from .models import (
    WorkflowTransitionDefinition,
    WorkItem,
    WorkItemAssignmentHistory,
    WorkItemCandidate,
    WorkItemStatus,
)
from .registry import SubjectAdapterSpec, registry

ASSIGNMENT_STATES = {
    "assigned": "تخصیص‌یافته",
    "candidate": "جهت اقدام",
    "claimed": "قبول‌شده",
    "delegated": "واگذاری موقت",
    "escalated": "نیازمند پیگیری بالاتر",
}
DUE_STATES = {
    "overdue": "گذشته از مهلت",
    "today": "امروز",
    "upcoming": "آینده",
    "no_due": "بدون مهلت",
}
PRIORITY_LEVELS = (
    ("urgent", "فوری"),
    ("high", "زیاد"),
    ("normal", "عادی"),
    ("low", "کم"),
)
ROUTING_LABELS = {
    "organization_owner": "مالک سازمان",
    "business_permission": "مجوز سازمانی",
    "explicit_membership": "انتخاب مستقیم عضویت",
    "organization_role": "نقش سازمانی",
    "position": "سمت سازمانی",
    "work_team": "تیم کاری",
    "record_creator": "ایجادکننده رکورد",
    "record_submitter": "ارسال‌کننده رکورد",
    "delegation": "واگذاری موقت",
    "escalation": "نیازمند پیگیری بالاتر",
    "explicit_reassignment": "تخصیص مجدد مستقیم",
}
OUTCOME_LABELS = {
    "approved": "تأیید",
    "rejected": "رد",
    "completed": "تکمیل",
}
HISTORY_ACTION_LABELS = {
    "claim": "قبول کار",
    "release": "واگذاری کار",
}


@dataclass(frozen=True, slots=True)
class WorkbenchCounts:
    all_items: int
    role_permission_items: int
    positions: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class WorkbenchData:
    queryset: models.QuerySet[WorkItem]
    membership: OrganizationMembership
    permission_codes: frozenset[str]
    counts: WorkbenchCounts
    filters: dict[str, tuple[tuple[str, str], ...]]


def _authorized_membership(
    *, actor: User, organization: Organization
) -> tuple[OrganizationMembership, frozenset[str]]:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORK_ITEMS_VIEW,
        message="اجازه مشاهده کارتابل این شرکت را ندارید.",
    )
    membership = get_active_membership(user=actor, organization=organization)
    if actor.is_superuser:
        return membership, frozenset(BusinessPermissionCode.values)
    codes = membership.role_definition.permissions.filter(is_active=True).values_list(
        "code", flat=True
    )
    return membership, frozenset(codes)


def _authorized_adapters(
    permission_codes: frozenset[str],
) -> dict[str, SubjectAdapterSpec]:
    return {
        item.subject_type: item
        for item in registry.subject_adapters.values()
        if not item.view_permission or item.view_permission in permission_codes
    }


def _candidate_subquery(
    *, organization: Organization, membership: OrganizationMembership
) -> models.QuerySet[WorkItemCandidate]:
    return WorkItemCandidate.objects.filter(
        organization=organization,
        work_item_id=OuterRef("pk"),
        membership=membership,
        is_active=True,
    )


def _base_queryset(
    *,
    organization: Organization,
    membership: OrganizationMembership,
    subject_types: tuple[str, ...],
    include_terminal: bool = False,
) -> models.QuerySet[WorkItem]:
    candidates = _candidate_subquery(organization=organization, membership=membership)
    queryset = (
        WorkItem.objects.filter(
            organization=organization,
            instance__subject_type__in=subject_types,
        )
        .filter(
            Q(current_assignee=membership)
            | (
                Q(status=WorkItemStatus.OPEN, current_assignee__isnull=True)
                & Exists(candidates)
            )
        )
        .annotate(
            is_candidate=Exists(candidates),
            is_delegated=Exists(
                candidates.filter(routing_basis__contains=[{"resolver": "delegation"}])
            ),
            is_escalated=Exists(
                candidates.filter(routing_basis__contains=[{"resolver": "escalation"}])
            ),
        )
    )
    if not include_terminal:
        queryset = queryset.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        )
    return queryset


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _priority_level(value: int) -> str:
    if value >= 80:
        return "urgent"
    if value >= 60:
        return "high"
    if value >= 25:
        return "normal"
    return "low"


def _priority_label(value: int) -> str:
    return dict(PRIORITY_LEVELS)[_priority_level(value)]


def _apply_filters(
    queryset: models.QuerySet[WorkItem],
    *,
    membership: OrganizationMembership,
    params: Mapping[str, Any],
) -> models.QuerySet[WorkItem]:
    workflow = str(params.get("workflow", "")).strip()
    if workflow:
        queryset = queryset.filter(instance__definition__workflow_type__code=workflow)

    project_id = _parse_uuid(str(params.get("project", "")).strip())
    if project_id:
        queryset = queryset.filter(
            instance__subject_context__project_id=str(project_id)
        )
    site_id = _parse_uuid(str(params.get("site", "")).strip())
    if site_id:
        queryset = queryset.filter(instance__subject_context__site_id=str(site_id))

    routing = str(params.get("routing", "")).strip()
    if routing == "role_permission":
        role_permission_candidate = WorkItemCandidate.objects.filter(
            organization_id=OuterRef("organization_id"),
            work_item_id=OuterRef("pk"),
            membership=membership,
            is_active=True,
        ).filter(
            Q(routing_basis__contains=[{"resolver": "business_permission"}])
            | Q(routing_basis__contains=[{"resolver": "organization_role"}])
            | Q(routing_basis__contains=[{"resolver": "organization_owner"}])
        )
        queryset = queryset.filter(Exists(role_permission_candidate))

    position_id = _parse_uuid(str(params.get("position", "")).strip())
    if position_id:
        position_candidate = WorkItemCandidate.objects.filter(
            organization_id=OuterRef("organization_id"),
            work_item_id=OuterRef("pk"),
            membership=membership,
            is_active=True,
        ).filter(
            Q(qualifying_position_assignment__position_id=position_id)
            | Q(routing_basis__contains=[{"position_id": str(position_id)}])
        )
        queryset = queryset.filter(
            Q(
                current_assignee=membership,
                assigned_via_position__position_id=position_id,
            )
            | Exists(position_candidate)
        )

    priority = str(params.get("priority", "")).strip()
    if priority == "urgent":
        queryset = queryset.filter(priority__gte=80)
    elif priority == "high":
        queryset = queryset.filter(priority__gte=60, priority__lt=80)
    elif priority == "normal":
        queryset = queryset.filter(priority__gte=25, priority__lt=60)
    elif priority == "low":
        queryset = queryset.filter(priority__lt=25)

    due = str(params.get("due", "")).strip()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    if due == "overdue":
        queryset = queryset.filter(due_at__lt=now)
    elif due == "today":
        queryset = queryset.filter(due_at__gte=today_start, due_at__lt=tomorrow)
    elif due == "upcoming":
        queryset = queryset.filter(due_at__gte=tomorrow)
    elif due == "no_due":
        queryset = queryset.filter(due_at__isnull=True)

    assignment = str(params.get("assignment", "")).strip()
    if assignment == "assigned":
        queryset = queryset.filter(
            status=WorkItemStatus.OPEN, current_assignee__isnull=False
        )
    elif assignment == "candidate":
        queryset = queryset.filter(
            is_candidate=True,
            status=WorkItemStatus.OPEN,
            current_assignee__isnull=True,
        )
    elif assignment == "claimed":
        queryset = queryset.filter(status=WorkItemStatus.CLAIMED)
    elif assignment == "delegated":
        queryset = queryset.filter(is_delegated=True)
    elif assignment == "escalated":
        queryset = queryset.filter(is_escalated=True)
    return queryset


def _ordered(
    queryset: models.QuerySet[WorkItem], params: Mapping[str, Any] | None = None
) -> models.QuerySet[WorkItem]:
    sort_fields = {
        "status": "status",
        "priority": "priority",
        "due_at": "due_at",
        "created_at": "created_at",
    }
    sort_key = str((params or {}).get("sort", "")).strip()
    if sort_key in sort_fields:
        direction = (
            "-" if str((params or {}).get("direction", "asc")).lower() == "desc" else ""
        )
        return queryset.order_by(f"{direction}{sort_fields[sort_key]}", "pk")
    now = timezone.now()
    return queryset.annotate(
        urgency_rank=Case(
            When(due_at__lt=now, then=Value(0)),
            When(due_at__isnull=False, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by("urgency_rank", "-priority", "due_at", "created_at", "pk")


def _position_counts(
    *,
    organization: Organization,
    membership: OrganizationMembership,
    subject_types: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    today = timezone.localdate()
    effective_positions = {
        str(item.pk): item.title
        for item in Position.objects.filter(
            organization=organization,
            employee_assignments__employee__user_id=membership.user_id,
            employee_assignments__status=PositionAssignmentStatus.ACTIVE,
            employee_assignments__start_date__lte=today,
        )
        .filter(
            Q(employee_assignments__end_date__isnull=True)
            | Q(employee_assignments__end_date__gte=today)
        )
        .distinct()
    }
    rows = WorkItemCandidate.objects.filter(
        organization=organization,
        membership=membership,
        is_active=True,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        work_item__instance__subject_type__in=subject_types,
    ).values(
        "work_item_id",
        "routing_basis",
        "qualifying_position_assignment__position_id",
        "qualifying_position_assignment__position__title",
    )
    work_items_by_position: dict[str, set[str]] = {}
    for row in rows:
        position_ids = {
            str(item["position_id"])
            for item in row["routing_basis"]
            if isinstance(item, dict) and item.get("position_id")
        }
        if row["qualifying_position_assignment__position_id"]:
            key = str(row["qualifying_position_assignment__position_id"])
            position_ids.add(key)
            effective_positions[key] = str(
                row["qualifying_position_assignment__position__title"]
            )
        for key in position_ids:
            work_items_by_position.setdefault(key, set()).add(str(row["work_item_id"]))
    unknown_position_ids = set(work_items_by_position) - set(effective_positions)
    if unknown_position_ids:
        effective_positions.update(
            {
                str(item.pk): item.title
                for item in Position.objects.filter(
                    organization=organization, pk__in=unknown_position_ids
                )
            }
        )
    return tuple(
        {
            "id": key,
            "label": label,
            "count": len(work_items_by_position.get(key, set())),
        }
        for key, label in sorted(effective_positions.items(), key=lambda item: item[1])
    )


def _filter_choices(
    *,
    organization: Organization,
    base: models.QuerySet[WorkItem],
    positions: tuple[dict[str, object], ...],
) -> dict[str, tuple[tuple[str, str], ...]]:
    workflows = tuple(
        (str(code), str(name))
        for code, name in base.values_list(
            "instance__definition__workflow_type__code",
            "instance__definition__workflow_type__name",
        )
        .distinct()
        .order_by("instance__definition__workflow_type__name")
    )
    priority_levels = {
        _priority_level(value)
        for value in base.values_list("priority", flat=True).distinct()
    }
    priorities = tuple(
        (value, label) for value, label in PRIORITY_LEVELS if value in priority_levels
    )
    projects = tuple(
        (str(item.pk), item.name)
        for item in Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")
    )
    sites = tuple(
        (str(item.pk), item.name)
        for item in ProjectSite.objects.filter(organization=organization).order_by(
            "project__name", "name"
        )
    )
    return {
        "workflow": workflows,
        "project": projects,
        "site": sites,
        "position": tuple((str(item["id"]), str(item["label"])) for item in positions),
        "priority": priorities,
        "due": tuple(DUE_STATES.items()),
        "assignment": tuple(ASSIGNMENT_STATES.items()),
    }


def build_workbench(
    *, actor: User, organization: Organization, params: Mapping[str, Any]
) -> WorkbenchData:
    membership, permission_codes = _authorized_membership(
        actor=actor, organization=organization
    )
    adapters = _authorized_adapters(permission_codes)
    subject_types = tuple(adapters)
    base = _base_queryset(
        organization=organization,
        membership=membership,
        subject_types=subject_types,
    )
    role_permission_items = _apply_filters(
        base,
        membership=membership,
        params={"routing": "role_permission"},
    ).count()
    positions = _position_counts(
        organization=organization,
        membership=membership,
        subject_types=subject_types,
    )
    filtered = _apply_filters(base, membership=membership, params=params)
    candidates = WorkItemCandidate.objects.filter(
        organization=organization, membership=membership, is_active=True
    ).select_related("qualifying_position_assignment__position")
    history = WorkItemAssignmentHistory.objects.filter(
        organization=organization
    ).select_related(
        "actor_membership__user", "from_membership__user", "to_membership__user"
    )
    transitions = WorkflowTransitionDefinition.objects.filter(
        organization=organization
    ).order_by("priority", "pk")
    queryset = (
        _ordered(filtered, params)
        .select_related(
            "instance__definition__workflow_type",
            "step_instance__step_definition",
            "current_assignee__user",
            "assigned_via_position__position",
        )
        .prefetch_related(
            Prefetch("candidates", queryset=candidates, to_attr="visible_candidates"),
            Prefetch("assignment_history", queryset=history, to_attr="visible_history"),
            Prefetch(
                "step_instance__step_definition__outgoing_transitions",
                queryset=transitions,
                to_attr="workbench_transitions",
            ),
        )
    )
    return WorkbenchData(
        queryset=queryset,
        membership=membership,
        permission_codes=permission_codes,
        counts=WorkbenchCounts(
            all_items=base.count(),
            role_permission_items=role_permission_items,
            positions=positions,
        ),
        filters=_filter_choices(
            organization=organization, base=base, positions=positions
        ),
    )


def _routing_reasons(item: WorkItem) -> tuple[str, ...]:
    evidence: list[dict[str, object]] = []
    for candidate in getattr(item, "visible_candidates", []):
        evidence.extend(candidate.routing_basis)
    if not evidence and item.current_assignee_id:
        evidence.extend(item.routing_basis)
    labels: list[str] = []
    for basis in evidence:
        label = ROUTING_LABELS.get(str(basis.get("resolver", "")), "مسیر ثبت‌شده")
        if label not in labels:
            labels.append(label)
    return tuple(labels) or ("تخصیص مستقیم کار",)


def _source_url(item: WorkItem, adapter: SubjectAdapterSpec) -> str:
    if not adapter.detail_url_name:
        return ""
    try:
        return reverse(
            adapter.detail_url_name,
            kwargs={adapter.detail_url_kwarg: item.instance.subject_id},
        )
    except NoReverseMatch:
        return ""


def decorate_work_items(
    items: list[WorkItem],
    *,
    membership: OrganizationMembership,
    permission_codes: frozenset[str],
) -> None:
    adapters = _authorized_adapters(permission_codes)
    can_claim_globally = BusinessPermissionCode.WORK_ITEMS_CLAIM in permission_codes
    can_act_globally = BusinessPermissionCode.WORK_ITEMS_ACT in permission_codes
    for item in items:
        candidate = bool(item.is_candidate)
        if item.status == WorkItemStatus.CLAIMED:
            state_label = ASSIGNMENT_STATES["claimed"]
            if item.current_assignee_id != membership.pk and item.current_assignee:
                assignee_user = item.current_assignee.user
                assignee_name = assignee_user.get_full_name() or assignee_user.username
                state_label = f"{state_label} توسط {assignee_name}"
            state = ("claimed", state_label)
        elif item.current_assignee:
            state_label = ASSIGNMENT_STATES["assigned"]
            if item.current_assignee_id != membership.pk:
                assignee_user = item.current_assignee.user
                assignee_name = assignee_user.get_full_name() or assignee_user.username
                state_label = f"{state_label} به {assignee_name}"
            state = ("assigned", state_label)
        else:
            state = ("candidate", ASSIGNMENT_STATES["candidate"])
        item.workbench_states = (state,)
        item.workbench_reasons = _routing_reasons(item)
        item.workbench_priority_label = _priority_label(item.priority)
        item.subject_title = str(
            item.instance.subject_context.get("subject_display")
            or item.instance.subject_id
        )
        adapter = adapters.get(item.instance.subject_type)
        item.source_url = _source_url(item, adapter) if adapter else ""
        is_safety = item.instance.subject_type == "safety.safety_incident"
        item.safety_responsible = (
            item.instance.subject_context.get("responsible_display", "")
            if is_safety
            else ""
        )
        item.can_claim_from_workbench = bool(
            can_claim_globally
            and candidate
            and item.status == WorkItemStatus.OPEN
            and item.current_assignee_id in (None, membership.pk)
        )
        item.can_release_from_workbench = bool(
            can_claim_globally
            and item.status == WorkItemStatus.CLAIMED
            and item.current_assignee_id == membership.pk
        )
        item.workbench_outcomes = []
        is_inventory_reversal = (
            item.instance.definition.workflow_type.code
            == "inventory.stock_transaction_reversal"
        )
        item.inventory_reversal_action_url = (
            item.source_url
            if is_inventory_reversal
            and can_act_globally
            and item.status == WorkItemStatus.CLAIMED
            and item.current_assignee_id == membership.pk
            else ""
        )
        item.safety_action_url = (
            item.source_url
            if is_safety
            and can_act_globally
            and item.status == WorkItemStatus.CLAIMED
            and item.current_assignee_id == membership.pk
            else ""
        )
        if (
            not is_safety
            and not is_inventory_reversal
            and can_act_globally
            and item.status == WorkItemStatus.CLAIMED
            and item.current_assignee_id == membership.pk
        ):
            for transition in item.step_instance.step_definition.workbench_transitions:
                required = transition.required_permission or item.required_permission
                if not required or required in permission_codes:
                    item.workbench_outcomes.append(
                        {
                            "value": transition.outcome,
                            "label": OUTCOME_LABELS.get(
                                transition.outcome, transition.outcome
                            ),
                            "token": uuid4().hex,
                        }
                    )
        history = list(getattr(item, "visible_history", []))[-5:]
        for entry in history:
            entry.workbench_action_label = HISTORY_ACTION_LABELS.get(
                entry.action, entry.get_action_display()
            )
        item.workbench_history = history
        item.operation_tokens = {
            "claim": uuid4().hex,
            "release": uuid4().hex,
        }


def get_workbench_item(
    *, actor: User, organization: Organization, work_item_id: object
) -> tuple[WorkItem, OrganizationMembership, frozenset[str]]:
    membership, permission_codes = _authorized_membership(
        actor=actor, organization=organization
    )
    subject_types = tuple(_authorized_adapters(permission_codes))
    queryset = (
        _base_queryset(
            organization=organization,
            membership=membership,
            subject_types=subject_types,
        )
        .select_related(
            "instance__definition__workflow_type",
            "step_instance__step_definition",
            "current_assignee__user",
            "assigned_via_position__position",
        )
        .prefetch_related(
            Prefetch(
                "candidates",
                queryset=WorkItemCandidate.objects.filter(
                    organization=organization, membership=membership, is_active=True
                ).select_related("qualifying_position_assignment__position"),
                to_attr="visible_candidates",
            ),
            Prefetch(
                "assignment_history",
                queryset=WorkItemAssignmentHistory.objects.filter(
                    organization=organization
                ).select_related(
                    "actor_membership__user",
                    "from_membership__user",
                    "to_membership__user",
                ),
                to_attr="visible_history",
            ),
            Prefetch(
                "step_instance__step_definition__outgoing_transitions",
                queryset=WorkflowTransitionDefinition.objects.filter(
                    organization=organization
                ).order_by("priority", "pk"),
                to_attr="workbench_transitions",
            ),
        )
    )
    try:
        item = queryset.get(pk=work_item_id)
    except (ValueError, WorkItem.DoesNotExist) as exc:
        raise PermissionDenied("این کار در کارتابل فعال شما وجود ندارد.") from exc
    decorate_work_items(
        [item], membership=membership, permission_codes=permission_codes
    )
    return item, membership, permission_codes
