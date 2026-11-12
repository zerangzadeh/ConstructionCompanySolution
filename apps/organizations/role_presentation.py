"""Presentation projections for the existing platform role catalogue."""

from django import forms
from django.core.paginator import Paginator
from django.urls import reverse

from apps.organizations.access_services import PRIVILEGED_TENANT_ROLES
from apps.organizations.permission_registry import PERMISSION_RESOURCES
from core.business_choices import SearchChoiceSelect

DOMAIN_LABELS = {
    "organizations": "شرکت، اعضا و دسترسی",
    "accounts": "حساب‌های کاربری",
    "projects": "پروژه‌ها و کنترل پروژه",
    "billing": "قراردادها و صورت‌وضعیت",
    "procurement": "تدارکات و خرید",
    "inventory": "انبار و موجودی",
    "workforce": "نیروی انسانی",
    "timekeeping": "حضور و کارکرد",
    "safety": "ایمنی",
    "quality": "کیفیت",
    "equipment": "تجهیزات",
    "daily_reports": "گزارش‌های روزانه",
    "expenses": "هزینه‌ها",
    "documents": "اسناد",
    "parties": "طرف‌های تجاری",
    "materials": "مصالح و واحدها",
    "workflows": "گردش کار",
    "accounting": "حسابداری",
    "treasury": "خزانه‌داری",
    "subledgers": "دریافتنی‌ها و پرداختنی‌ها",
    "payroll": "حقوق و دستمزد",
    "reporting": "گزارش‌گیری",
    "support": "پشتیبانی",
    "knowledge": "دانش سازمانی",
    "partners": "همکاران",
    "compliance": "انطباق",
    "audit": "ممیزی",
    "fixed_assets": "دارایی‌های ثابت",
    "commercial": "تعهدات و اسناد تجاری",
    "contracts": "قراردادها",
    "estimates": "برآوردها",
    "financials": "گزارش‌های مالی",
    "partner_qualification": "صلاحیت همکاران",
}


def tenant_selector(organizations, selected=None):
    """Enhance the existing allowed tenant choices; never resolve active scope."""
    field = forms.ModelChoiceField(
        label="شرکت هدف",
        queryset=organizations,
        empty_label="انتخاب شرکت",
        widget=SearchChoiceSelect(
            attrs={
                "data-business-choice": "true",
                "data-local-choices": "true",
                "data-hide-enhanced-source": "true",
                "data-placeholder": "جست‌وجو و انتخاب شرکت…",
            }
        ),
    )
    selector = forms.Form(initial={"organization": selected})
    selector.fields["organization"] = field
    return selector


def role_is_protected(role):
    return bool(
        role
        and role.is_system
        and (role.is_owner or role.code in PRIVILEGED_TENANT_ROLES)
    )


def permission_groups(form, role):
    """Group exact form choices by their registered owning Django app.

    Unknown/retired assignments stay visible but cannot be silently removed by
    this editor. The form queryset and audited services remain authoritative.
    """
    resources = {}
    for resource in PERMISSION_RESOURCES:
        for code in resource.permissions:
            resources.setdefault(str(code), resource)
    choices = list(form.fields["permissions"].queryset)
    allowed_ids = {str(permission.pk) for permission in choices}
    assigned = list(role.permissions.all()) if role else []
    unavailable = [p for p in assigned if str(p.pk) not in allowed_ids]
    selected = {str(value) for value in (form["permissions"].value() or [])}
    groups = {}
    for permission in choices + unavailable:
        resource = resources.get(permission.code)
        module = resource.enforcement_modules[0] if resource else ""
        owner = module.split(".")[1] if module.startswith("apps.") else "other"
        label = DOMAIN_LABELS.get(owner, "سایر منابع ثبت‌شده")
        group = groups.setdefault(label, {"label": label, "items": [], "selected": 0})
        checked = str(permission.pk) in selected or permission in unavailable
        group["items"].append(
            {
                "permission": permission,
                "selected": checked,
                "unavailable": permission in unavailable,
                "resource": resource.label if resource else "منبع بدون دسته‌بندی",
            }
        )
        group["selected"] += checked
    return sorted(groups.values(), key=lambda group: group["label"]), unavailable


def workspace_context(request, context):
    roles = context["roles"]
    page = Paginator(roles, 10).get_page(request.GET.get("page"))
    for role in page.object_list:
        role.presentation_protected = role_is_protected(role)
    role = context["selected_role"]
    form = context["form"]
    groups, unavailable = permission_groups(form, role)
    params = request.GET.copy()
    for name in ("edit", "mode", "new"):
        params.pop(name, None)
    base_url = reverse("organizations:platform_role_catalog")

    def url(**changes):
        query = params.copy()
        query.update(changes)
        return f"{base_url}?{query.urlencode()}"

    context.update(
        {
            "roles": page.object_list,
            "page_obj": page,
            "pagination_rendered": True,
            "permission_groups": groups,
            "permission_total": sum(len(group["items"]) for group in groups),
            "permission_selected": sum(group["selected"] for group in groups),
            "permissions_locked": role_is_protected(role),
            "unavailable_permissions": unavailable,
            "can_edit_role": (
                not context["tenant_mode"]
                or context["catalog_organization"] is not None
            )
            and (not role or (role.is_active and not unavailable)),
            "editing": bool(
                form.is_bound
                or request.GET.get("mode") == "edit"
                or request.GET.get("new") == "1"
            ),
            "creating": request.GET.get("new") == "1" or (form.is_bound and not role),
            "view_url": url(edit=role.pk) if role else url(),
            "edit_url": url(edit=role.pk, mode="edit") if role else url(new="1"),
            "new_url": url(new="1"),
            "role_kind": request.GET.get("kind", ""),
            "role_status": request.GET.get("status", ""),
            "tenant_selector": tenant_selector(
                context["organizations"], context["catalog_organization"]
            ),
        }
    )
    return context
