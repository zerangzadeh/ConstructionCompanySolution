"""Platform console views backed by existing control-plane sources."""

from datetime import timedelta
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import caches
from django.core.cache.backends.dummy import DummyCache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.platform_user_services import (
    ACCOUNT_AUDIT_ACTIONS,
    user_management_permissions,
)
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations import views
from apps.organizations.access_services import (
    assign_platform_role,
    revoke_platform_role,
)
from apps.organizations.authorization import has_business_permission, is_platform_admin
from apps.organizations.form_scoping import normalized_uuid
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.platform_companies import incomplete_company_onboarding
from apps.organizations.platform_grants import lock_platform_admin
from core.forms import JalaliDateMixin
from core.jalali import format_jalali
from core.list_filters import paginate_table
from core.operations import (
    dependency_signals,
    probe_cache,
    probe_database,
    recent_operations_alerts,
)
from core.product_surface import CAPABILITIES, surface_profile

PLATFORM_AUDIT_ACTIONS = (
    AuditAction.PLATFORM_ROLE_ASSIGNED,
    AuditAction.PLATFORM_ROLE_REVOKED,
    AuditAction.PROTECTED_OPERATION_CLASSIFIED,
    AuditAction.PROTECTED_OPERATION_RETIRED,
    AuditAction.ORGANIZATION_CREATED,
    AuditAction.ORGANIZATION_STATUS_CHANGED,
    AuditAction.ORGANIZATION_SETTINGS_UPDATED,
    AuditAction.ORGANIZATION_ONBOARDING_RETRIED,
    AuditAction.ROLE_CREATED,
    AuditAction.ROLE_UPDATED,
    AuditAction.ROLE_ARCHIVED,
    AuditAction.PLATFORM_POLICY_CREATED,
    AuditAction.PLATFORM_POLICY_VERSION_CREATED,
    AuditAction.PLATFORM_POLICY_VERSION_UPDATED,
    AuditAction.PLATFORM_POLICY_VERSION_PUBLISHED,
    AuditAction.PLATFORM_POLICY_VERSION_RETIRED,
    AuditAction.PLATFORM_POLICY_DEACTIVATED,
    *ACCOUNT_AUDIT_ACTIONS,
)

CAPABILITY_LABELS = {
    "entry": "ورود و حساب کاربری",
    "projects": "پروژه‌ها",
    "daily_reports": "گزارش روزانه",
    "timekeeping": "حضور و کارکرد",
    "equipment": "تجهیزات",
    "expenses": "هزینه‌ها",
    "safety": "ایمنی",
    "quality": "کیفیت",
    "contracts": "قرارداد و صورت‌وضعیت",
    "procurement": "تدارکات و انبار",
    "shared": "اسناد و خدمات مشترک",
    "organization": "مدیریت شرکت",
    "field_workforce": "نیروی کارگاهی",
    "operational_reports": "گزارش‌های عملیاتی",
    "full_hr": "منابع انسانی کامل",
    "internal_reporting": "گزارش‌های داخلی",
    "technical_administration": "مدیریت فنی",
    "finance": "مالی، حسابداری و خزانه",
    "payroll": "حقوق و دستمزد",
    "commercial": "بازرگانی تکمیلی",
    "compliance": "انطباق و ارزیابی شرکا",
    "support": "پشتیبانی و دانش",
}

ALERT_LABELS = {
    "database.unreachable": "قطع دسترسی پایگاه داده",
    "cache.unreachable": "قطع دسترسی حافظهٔ نهان",
    "http.server_error": "خطای سرور",
    "telemetry.delivery_failed": "خطا در ثبت رخداد عملیاتی",
    "authentication.failed": "ورود ناموفق",
    "authorization.denied": "رد دسترسی",
    "document.delivery_failed": "تحویل ناموفق سند",
    "migration.failed": "اجرای ناموفق مهاجرت",
    "deployment.failed": "استقرار ناموفق",
    "backup.failed": "پشتیبان‌گیری ناموفق",
    "recovery.failed": "بازیابی ناموفق",
    "operational.not_ready": "اعلام آمادگی ناموفق",
}


class OperatorForm(forms.Form):
    username = forms.CharField(label="نام کاربری", max_length=150)
    reason = forms.CharField(label="دلیل", max_length=1000)


class OperatorRevocationForm(forms.Form):
    assignment = forms.UUIDField()
    reason = forms.CharField(label="دلیل لغو", max_length=1000)


class PlatformAuditFilter(JalaliDateMixin, forms.Form):
    start = forms.DateField(
        label="از تاریخ شمسی",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end = forms.DateField(
        label="تا تاریخ شمسی",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    actor = forms.CharField(label="نام کاربری عامل", required=False, max_length=150)
    action = forms.ChoiceField(
        label="عملیات",
        required=False,
        choices=(
            ("", "همه عملیات"),
            *((code.value, code.label) for code in PLATFORM_AUDIT_ACTIONS),
        ),
    )
    company = forms.ModelChoiceField(
        label="شرکت",
        required=False,
        queryset=Organization.objects.order_by("name", "pk"),
    )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            self.add_error("end", "تاریخ پایان باید از تاریخ شروع زودتر نباشد.")
        return data


def _require_admin(
    request: HttpRequest, permission: BusinessPermissionCode | None = None
):
    if not is_platform_admin(request.user) or (
        permission is not None
        and not BusinessPermission.objects.filter(
            code=permission, is_active=True
        ).exists()
    ):
        raise PermissionDenied("دسترسی مدیر پلتفرم لازم است.")


def _platform_events():
    return (
        AuditEvent.objects.filter(action__in=PLATFORM_AUDIT_ACTIONS)
        .filter(
            Q(organization__isnull=True) & ~Q(action__in=ACCOUNT_AUDIT_ACTIONS)
            | Q(
                action__in=(
                    AuditAction.ORGANIZATION_STATUS_CHANGED,
                    AuditAction.ORGANIZATION_ONBOARDING_RETRIED,
                )
            )
            | Q(metadata__control_plane=True)
        )
        .select_related("actor", "organization")
        .only(
            "action", "created_at", "actor__username", "organization__name", "entity_id"
        )
        .order_by("-created_at", "-pk")
    )


def _health_signals():
    signals = dependency_signals(database=probe_database, cache=probe_cache)
    return [
        "cache.unverified"
        if signal == "cache.reachable" and isinstance(caches["default"], DummyCache)
        else signal
        for signal in signals
    ]


@login_required
@require_GET
@never_cache
def dashboard(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    companies = Organization.objects.filter(deleted_at__isnull=True)
    counts = companies.aggregate(
        total=Count("pk"),
        active=Count(
            "pk", filter=Q(status=OrganizationStatus.ACTIVE, archived_at__isnull=True)
        ),
        suspended=Count(
            "pk",
            filter=Q(status=OrganizationStatus.SUSPENDED, archived_at__isnull=True),
        ),
        cancelled=Count(
            "pk",
            filter=Q(status=OrganizationStatus.CANCELLED, archived_at__isnull=True),
        ),
        archived=Count(
            "pk",
            filter=Q(status=OrganizationStatus.ARCHIVED),
        ),
    )
    newest = list(
        companies.filter(
            status=OrganizationStatus.ACTIVE, archived_at__isnull=True
        ).order_by("-created_at", "-pk")[:5]
    )
    can_audit = BusinessPermission.objects.filter(
        code=BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_AUDIT, is_active=True
    ).exists()
    can_probe = BusinessPermission.objects.filter(
        code=BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_HEALTH, is_active=True
    ).exists()
    checked_at = timezone.now()
    events = _platform_events() if can_audit else AuditEvent.objects.none()
    window_start = timezone.localtime(checked_at).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=6)
    daily_activity = dict(
        events.filter(created_at__gte=window_start, created_at__lte=checked_at)
        .annotate(day=TruncDate("created_at"))
        .order_by()
        .values("day")
        .annotate(total=Count("pk"))
        .values_list("day", "total")
    )
    activity_total = sum(daily_activity.values())
    activity_rows = (
        [
            {
                "label": format_jalali(window_start.date() + timedelta(days=offset))[
                    5:
                ],
                "value": daily_activity.get(
                    window_start.date() + timedelta(days=offset), 0
                ),
            }
            for offset in range(7)
        ]
        if activity_total
        else []
    )
    status_rows = (
        [
            {"label": str(label), "value": counts[status], "status": status}
            for status, label in OrganizationStatus.choices
        ]
        if counts["total"]
        else []
    )
    charts = [
        {
            "id": "platform-company-status",
            "type": "doughnut",
            "rows": status_rows,
            "unit": "شرکت",
        },
        {
            "id": "platform-weekly-activity",
            "type": "bar",
            "rows": activity_rows,
            "unit": "رویداد",
        },
    ]
    registered_users = User.objects.count()
    memberships = OrganizationMembership.objects.count()
    can_view_users = (
        BusinessPermissionCode.PLATFORM_ADMIN_USERS_VIEW
        in user_management_permissions(request.user)
    )
    return render(
        request,
        "organizations/platform_dashboard.html",
        {
            "platform_workspace": True,
            "counts": counts,
            "registered_users": registered_users,
            "memberships": memberships,
            "kpis": [
                {
                    "label": "همه شرکت‌ها",
                    "value": counts["total"],
                    "icon": "layers",
                    "tone": "companies",
                },
                {
                    "label": "شرکت‌های فعال",
                    "value": counts["active"],
                    "icon": "company",
                    "tone": "active",
                },
                {
                    "label": "شرکت‌های تعلیق‌شده",
                    "value": counts["suspended"],
                    "icon": "pause",
                    "tone": "suspended",
                },
                {
                    "label": "حساب‌های ثبت‌شده",
                    "value": registered_users,
                    "icon": "users",
                    "tone": "accounts",
                    "url": reverse("organizations:platform_users")
                    if can_view_users
                    else None,
                },
                {
                    "label": "عضویت‌های ثبت‌شده",
                    "value": memberships,
                    "icon": "id-card",
                    "tone": "memberships",
                },
            ],
            "onboarding_warnings": [
                company for company in newest if incomplete_company_onboarding(company)
            ],
            "events": events[:4],
            "health_signals": _health_signals() if can_probe else (),
            "can_audit": can_audit,
            "can_probe": can_probe,
            "can_manage_operators": BusinessPermission.objects.filter(
                code=BusinessPermissionCode.PLATFORM_ADMIN_MANAGE_OPERATORS,
                is_active=True,
            ).exists(),
            "checked_at": checked_at,
            "can_view_platform_users": can_view_users,
            "company_status_rows": status_rows,
            "activity_rows": activity_rows,
            "activity_total": activity_total,
            "dashboard_charts": charts,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def administrators(request: HttpRequest) -> HttpResponse:
    _require_admin(request, BusinessPermissionCode.PLATFORM_ADMIN_MANAGE_OPERATORS)
    form = OperatorForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "grant"
        else None
    )
    if request.method == "POST":
        if request.POST.get("action") == "revoke":
            revoke_form = OperatorRevocationForm(request.POST)
            if not revoke_form.is_valid():
                messages.error(request, "شناسه و دلیل لغو را بررسی کنید.")
            else:
                try:
                    revoke_platform_role(
                        actor=request.user,
                        assignment_id=revoke_form.cleaned_data["assignment"],
                        reason=revoke_form.cleaned_data["reason"],
                    )
                except (PermissionDenied, ValidationError) as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "دسترسی مدیر پلتفرم لغو شد.")
            return redirect("organizations:platform_administrators")
        if request.POST.get("action") != "grant":
            raise PermissionDenied("عملیات مدیریت مدیران معتبر نیست.")
        if form.is_valid():
            target = User.objects.filter(
                username__iexact=form.cleaned_data["username"], is_active=True
            ).first()
            if target is None:
                form.add_error("username", "حساب فعال یافت نشد.")
            else:
                try:
                    assign_platform_role(
                        actor=request.user,
                        target=target,
                        role=PlatformRoleCode.PLATFORM_ADMIN,
                        reason=form.cleaned_data["reason"],
                    )
                except (PermissionDenied, ValidationError) as exc:
                    form.add_error(None, str(exc))
                else:
                    messages.success(request, "دسترسی مدیر پلتفرم ثبت شد.")
                    return redirect("organizations:platform_administrators")
    page = paginate_table(
        PlatformRoleAssignment.objects.filter(
            role=PlatformRoleCode.PLATFORM_ADMIN
        ).select_related("user", "assigned_by", "revoked_by"),
        request,
        sort_fields={},
        default_ordering=("-starts_at", "-pk"),
    )
    return render(
        request,
        "organizations/platform_administrators.html",
        {
            "platform_workspace": True,
            "page_obj": page,
            "pagination_rendered": True,
            "assignments": page.object_list,
            "form": form,
            "now": timezone.now(),
        },
    )


@login_required
@require_GET
@never_cache
def audit_log(request: HttpRequest) -> HttpResponse:
    _require_admin(request, BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_AUDIT)
    form = PlatformAuditFilter(request.GET)
    events = _platform_events()
    if form.is_valid():
        data = form.cleaned_data
        if data["start"]:
            events = events.filter(created_at__date__gte=data["start"])
        if data["end"]:
            events = events.filter(created_at__date__lte=data["end"])
        if data["actor"]:
            events = events.filter(actor__username__icontains=data["actor"])
        if data["action"]:
            events = events.filter(action=data["action"])
        if data["company"]:
            events = events.filter(organization=data["company"])
    else:
        events = events.none()
    page = paginate_table(
        events.annotate(
            previous_status=KeyTextTransform(
                "before", KeyTransform("status", "changes")
            ),
            new_status=KeyTextTransform("after", KeyTransform("status", "changes")),
        ),
        request,
        sort_fields={},
        default_ordering=("-created_at", "-pk"),
    )
    labels = dict(OrganizationStatus.choices)
    rows = [
        (
            event,
            normalized_uuid(event.entity_id),
            labels.get(event.previous_status),
            labels.get(event.new_status),
        )
        for event in page.object_list
    ]
    return render(
        request,
        "organizations/platform_audit.html",
        {
            "platform_workspace": True,
            "rows": rows,
            "page_obj": page,
            "pagination_rendered": True,
            "form": form,
        },
    )


@login_required
@require_GET
def platform_settings(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    return render(
        request,
        "organizations/platform_settings.html",
        {
            "platform_workspace": True,
            "profile": surface_profile(),
            "capabilities": [
                (CAPABILITY_LABELS[capability.key], capability.mvp)
                for capability in CAPABILITIES
            ],
        },
    )


@login_required
@require_GET
@never_cache
def system_status(request: HttpRequest) -> HttpResponse:
    _require_admin(request, BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_HEALTH)
    alerts = recent_operations_alerts()
    return render(
        request,
        "organizations/platform_status.html",
        {
            "platform_workspace": True,
            "health_signals": _health_signals(),
            "checked_at": timezone.now(),
            "alert_source_available": alerts is not None,
            "alerts": [
                (observed, ALERT_LABELS[signal])
                for observed, signal in (alerts or ())
                if signal in ALERT_LABELS
            ],
        },
    )


def _can_inspect_member_roles(request: HttpRequest, company: Organization) -> bool:
    return all(
        has_business_permission(
            user=request.user, organization=company, permission=permission
        )
        for permission in (
            BusinessPermissionCode.MEMBERSHIP_VIEW,
            BusinessPermissionCode.AUTHORIZATION_ROLES_VIEW,
        )
    )


@login_required
@require_GET
@never_cache
def member_roles(request: HttpRequest) -> HttpResponse:
    from apps.organizations.role_presentation import tenant_selector

    _require_admin(request)
    companies = Organization.objects.filter(
        status=OrganizationStatus.ACTIVE,
        archived_at__isnull=True,
        deleted_at__isnull=True,
    )
    company = None
    page = None
    if request.GET.get("organization"):
        company = get_object_or_404(
            companies, pk=normalized_uuid(request.GET["organization"])
        )
        if _can_inspect_member_roles(request, company):
            now = timezone.now()
            members = (
                company.memberships.select_related("user", "role_definition")
                .prefetch_related(
                    Prefetch(
                        "role_assignments",
                        queryset=MembershipRoleAssignment.objects.filter(
                            revoked_at__isnull=True,
                            starts_at__lte=now,
                            role__is_active=True,
                        )
                        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
                        .select_related("role"),
                        to_attr="current_roles",
                    )
                )
                .annotate(assignment_count=Count("role_assignments"))
            )
            query = request.GET.get("q", "").strip()[:150]
            if query:
                members = members.filter(user__username__icontains=query)
            page = paginate_table(
                members,
                request,
                sort_fields={},
                default_ordering=("user__username", "pk"),
            )
    return render(
        request,
        "organizations/platform_member_roles.html",
        {
            "platform_workspace": True,
            "platform_target": company,
            "companies": companies.order_by("name", "pk"),
            "tenant_selector": tenant_selector(
                companies.order_by("name", "pk"), company
            ),
            "company": company,
            "page_obj": page,
            "can_inspect": page is not None,
            "pagination_rendered": True,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def member_authorization(
    request: HttpRequest, organization_id: UUID, membership_id: UUID
) -> HttpResponse:
    _require_admin(request)
    company = get_object_or_404(Organization, pk=organization_id)
    if not _can_inspect_member_roles(request, company):
        raise PermissionDenied("مجوز مشاهده نقش‌های اعضای این شرکت لازم است.")
    if request.method == "POST":
        with transaction.atomic():
            lock_platform_admin(request.user)
            return views.member_authorization_response(
                request, company, membership_id, platform_mode=True
            )
    return views.member_authorization_response(
        request, company, membership_id, platform_mode=True
    )
