"""HTTP adapters for existing claim services; no new calculation or workflow rules."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.contracts.forms import ContractForm
from apps.estimates.forms import EstimateForm, EstimateItemForm
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from core.business_choices import business_label, contextual_url

from .journey_forms import ClaimCorrectionForm, ClaimCreateForm, ClaimDecisionForm
from .services import (
    approve_progress_claim,
    create_progress_claim,
    create_progress_claim_correction,
    get_progress_claims,
    recalculate_progress_claim,
    return_progress_claim,
    submit_progress_claim,
)


def claim_create_allowed(request):
    return all(
        has_business_permission(
            user=request.user, organization=request.organization, permission=p
        )
        for p in (
            P.CLAIMS_VIEW,
            P.CLAIMS_CREATE,
            P.CLAIMS_REVISE,
            P.CONTRACTS_VIEW,
            P.BASELINES_VIEW,
        )
    )


def journey_breadcrumbs(title, contract=None, *, collection=None):
    from core.product_surface import NAVIGATION_GROUPS

    group_label = next(
        group.label for group in NAVIGATION_GROUPS if group.key == "claims"
    )
    crumbs = [
        {"label": "خانه", "url": reverse("home")},
        {"label": group_label, "url": ""},
    ]
    if contract:
        crumbs.append({"label": "قراردادها", "url": reverse("contracts:list")})
        crumbs.append(
            {
                "label": contract.title,
                "url": reverse("contracts:detail", args=[contract.pk]),
            }
        )
    elif collection:
        crumbs.append({"label": collection[0], "url": reverse(collection[1])})
    crumbs.append({"label": title, "url": ""})
    return crumbs


def error_text(exc):
    text = " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
    text = text.replace("پین‌شده", "ثبت‌شده برای این صورت‌وضعیت")
    return {
        "کار فعال و نامزدی معتبر برای صورت‌وضعیت وجود ندارد.": "این صورت‌وضعیت در مسئولیت بررسی شما نیست.",
        "کار به عضویت دیگری تخصیص یافته است.": "بررسی این صورت‌وضعیت به فرد دیگری سپرده شده است.",
    }.get(text, text)


@active_organization_required
@require_GET
def choices(request, purpose, kind):
    permission = {
        "estimate": P.ESTIMATES_CREATE,
        "estimate_item": P.ESTIMATE_ITEMS_ADD,
        "contract": P.CONTRACTS_CREATE,
        "claim": P.CLAIMS_CREATE,
    }.get(purpose)
    if not permission or not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=permission,
        allow_any_scope=True,
    ):
        raise PermissionDenied
    kwargs = {"organization": request.organization}
    if purpose == "claim":
        form = ClaimCreateForm(request.GET, actor=request.user, **kwargs)
    elif purpose == "estimate_item":
        form = EstimateItemForm(**kwargs)
    else:
        form = {"estimate": EstimateForm, "contract": ContractForm}[purpose](
            request.GET,
            membership=get_active_membership(
                user=request.user, organization=request.organization
            ),
            **kwargs,
        )
    allowed = {
        "estimate": ("project", "contract", "phase"),
        "estimate_item": ("unit_of_measure",),
        "contract": ("project", "party"),
        "claim": ("contract", "baseline"),
    }
    if kind not in allowed[purpose]:
        raise PermissionDenied
    records = form.fields[kind].queryset
    search_fields = {
        "project": ("name", "code"),
        "contract": ("title", "contract_number", "project__name"),
        "party": ("display_name",),
        "phase": ("name", "site__name"),
        "unit_of_measure": ("name", "symbol"),
        "baseline": ("contract__title", "contract__contract_number"),
    }[kind]
    query = request.GET.get("q", "").strip()[:200]
    if query:
        search = Q()
        for name in search_fields:
            search |= Q(**{f"{name}__icontains": query})
        records = records.filter(search)
    try:
        page = max(1, min(int(request.GET.get("page", 1)), 100000))
    except (TypeError, ValueError):
        page = 1
    records = records.order_by(*(records.query.order_by or (search_fields[0],)), "pk")
    rows = list(records[(page - 1) * 40 : page * 40 + 1])
    querystring = request.GET.copy()
    querystring["page"] = page + 1
    response = JsonResponse(
        {
            "results": [
                {"value": str(row.pk), "label": business_label(row)}
                for row in rows[:40]
            ],
            "next": f"{request.path}?{querystring.urlencode()}"
            if len(rows) > 40
            else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response


@active_organization_required
@organization_permission_required(P.CLAIMS_CREATE)
@require_http_methods(["GET", "POST"])
def claim_create(request):
    if not claim_create_allowed(request):
        raise PermissionDenied(
            "برای ایجاد صورت‌وضعیت، دسترسی به قرارداد، مبنا و محاسبه لازم است."
        )
    initial = {
        name: request.GET.get(name)
        for name in ("contract", "baseline")
        if request.GET.get(name)
    }
    form = ClaimCreateForm(
        request.POST if request.method == "POST" else None,
        organization=request.organization,
        actor=request.user,
        active_project=request.active_project,
        initial=initial,
    )
    if (
        request.method == "POST"
        and request.POST.get("_refresh_choices") != "1"
        and form.is_valid()
    ):
        try:
            claim = create_progress_claim(
                organization=request.organization,
                actor=request.user,
                **{
                    name: form.cleaned_data[name]
                    for name in (
                        "baseline",
                        "period_start",
                        "period_end",
                        "measurement_cutoff",
                    )
                },
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, error_text(exc))
        else:
            messages.success(request, "پیش‌نویس صورت‌وضعیت با کسور محاسبه‌شده ایجاد شد.")
            return redirect("billing:claim_detail", claim_id=claim.pk)
    return render(
        request,
        "billing/claim_form.html",
        {
            "form": form,
            "cancel_url": contextual_url(
                "billing:claim_list", contract=form.selected_contract
            ),
            "page_breadcrumbs": journey_breadcrumbs(
                "صورت‌وضعیت جدید", collection=("صورت‌وضعیت‌ها", "billing:claim_list")
            ),
        },
    )


@active_organization_required
@require_POST
def claim_action(request, claim_id, action):
    permissions = {
        "recalculate": P.CLAIMS_REVISE,
        "submit": P.CLAIMS_SUBMIT,
        "approve": P.CLAIMS_APPROVE,
        "return": P.CLAIMS_APPROVE,
        "correct": P.CLAIMS_REVISE,
    }
    permission = permissions.get(action)
    if not permission or not has_business_permission(
        user=request.user, organization=request.organization, permission=permission
    ):
        raise PermissionDenied
    claim = get_object_or_404(
        get_progress_claims(actor=request.user, organization=request.organization),
        pk=claim_id,
    )
    form = (
        ClaimCorrectionForm(request.POST)
        if action == "correct"
        else ClaimDecisionForm(request.POST)
    )
    if action in ("approve", "return", "correct") and not form.is_valid():
        from .views import render_claim_detail

        return render_claim_detail(request, claim_id, action_form=form)
    try:
        if action == "correct":
            claim = create_progress_claim_correction(
                organization=request.organization,
                actor=request.user,
                claim=claim,
                **form.cleaned_data,
            )
        else:
            service = {
                "recalculate": recalculate_progress_claim,
                "submit": submit_progress_claim,
                "approve": approve_progress_claim,
                "return": return_progress_claim,
            }[action]
            kwargs = (
                {"reason": form.cleaned_data["reason"]}
                if action in ("approve", "return")
                else {}
            )
            service(
                organization=request.organization,
                actor=request.user,
                claim=claim,
                **kwargs,
            )
        messages.success(
            request,
            {
                "recalculate": "مقادیر و کسور پیش‌نویس به‌روز شد.",
                "submit": "صورت‌وضعیت برای بررسی ارسال شد.",
                "approve": "صورت‌وضعیت تأیید شد.",
                "return": "صورت‌وضعیت بازگردانده و نسخه اصلاحی ایجاد شد.",
                "correct": "نسخه اصلاحی ایجاد شد؛ نسخه قبلی تا تأیید نسخه جدید حفظ می‌شود.",
            }[action],
        )
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, error_text(exc))
    return redirect("billing:claim_detail", claim_id=claim.pk)
