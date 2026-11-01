"""State-aware presentation and HTTP form adapters; domain services retain authority."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from core.product_surface import route_exposed

from .detail_forms import (
    ContractTermDraftForm,
    DraftContractEditForm,
    DraftContractItemForm,
)
from .models import Contract, ContractDirection, ContractStatus, ContractType
from .services import (
    add_contract_item,
    create_contract_term_version,
    get_organization_contracts,
    update_draft_contract,
)


def contract_workspace(request: HttpRequest, contract: Contract, terms: list) -> dict:
    def access(permission):
        return has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=contract.project,
        )

    draft = contract.status == ContractStatus.DRAFT
    receivable = contract.direction == ContractDirection.RECEIVABLE
    payable = (
        contract.direction == ContractDirection.PAYABLE
        and contract.contract_type == ContractType.SUBCONTRACT
    )
    supports_terms = receivable or payable
    items = list(contract.items.all())
    approved_terms = [term for term in terms if term.status == "approved"]
    draft_terms = [term for term in terms if term.status == "draft"]
    base_complete = bool(
        contract.title
        and contract.counterparty_name
        and contract.direction
        and contract.contract_type
        and (contract.party_id or not supports_terms)
    )
    can_edit = draft and access(P.CONTRACTS_CHANGE)
    can_add_item = draft and access(P.CONTRACT_ITEMS_ADD)
    can_terms = (
        supports_terms
        and contract.status in ("draft", "active", "completed")
        and access(P.CONTRACT_TERMS_MANAGE)
    )
    term_status = (
        "نسخه تأییدشده دارد"
        if approved_terms
        else "پیش‌نویس تهیه شده"
        if draft_terms
        else "نیازمند تهیه شرایط"
    )
    readiness = [
        {
            "label": "اطلاعات پایه",
            "value": "ثبت‌شده" if base_complete else "نیازمند تکمیل",
            "ready": base_complete,
            "url": "#information",
        },
        {
            "label": "ردیف‌های قرارداد",
            "value": f"{len(items)} ردیف" if items else "هنوز ردیفی ثبت نشده",
            "ready": bool(items),
            "url": "#items",
        },
    ]
    if supports_terms:
        readiness.append(
            {
                "label": "شرایط قرارداد",
                "value": term_status,
                "ready": bool(terms),
                "url": "#terms",
            }
        )
    preparation_complete = all(row["ready"] for row in readiness)
    readiness.append(
        {
            "label": "مرور پیش‌نویس",
            "value": "اطلاعات آماده مرور است"
            if preparation_complete
            else "بخش‌های نیازمند تکمیل را بررسی کنید",
            "ready": preparation_complete,
            "url": "#draft-review",
        }
    )
    action = request.POST.get("detail_action", "") if request.method == "POST" else ""
    forms = {}
    if can_edit:
        forms["edit_base"] = DraftContractEditForm(
            request.POST if action == "edit_base" else None,
            organization=request.organization,
            contract=contract,
        )
    if can_add_item:
        forms["add_item"] = DraftContractItemForm(
            request.POST if action == "add_item" else None,
            organization=request.organization,
        )
    if can_terms:
        latest = max(terms, key=lambda term: term.version) if terms else None
        initial = (
            {
                name: getattr(latest, name)
                for name in (
                    "payment_due_days",
                    "retention_rate",
                    "retention_cap",
                    "advance_recovery_rate",
                    "advance_recovery_cap",
                    "contractual_insurance_rate",
                    "contractual_insurance_cap",
                    "retention_release_requirement",
                    "retention_release_cap",
                )
            }
            if latest
            else {}
        )
        initial["insurance_classification"] = (
            latest.insurance_classification_id if latest else None
        )
        forms["create_term"] = ContractTermDraftForm(
            request.POST if action == "create_term" else None,
            on_date=(
                latest.effective_from
                if draft and latest
                else contract.start_date
                if draft and contract.start_date
                else timezone.localdate()
            ),
            initial=initial,
        )
    return {
        "is_draft": draft,
        "receivable": receivable,
        "payable": payable,
        "supports_operations": receivable or payable,
        "supports_terms": supports_terms,
        "is_supplier": contract.direction == "payable"
        and contract.contract_type == "supplier",
        "can_edit": can_edit,
        "can_add_item": can_add_item,
        "can_terms": can_terms,
        "forms": forms,
        "base_form": forms.get("edit_base"),
        "item_form": forms.get("add_item"),
        "term_form": forms.get("create_term"),
        "readiness": readiness,
        "item_count": len(items),
        "items_total": sum((item.line_total for item in items), Decimal(0)),
        "term_status": term_status,
        "billing_empty_note": (
            "برای این قرارداد خاتمه‌یافته صورت‌وضعیتی ثبت نشده است؛ سوابق موجود فقط برای بازبینی نمایش داده می‌شوند."
            if contract.status == "terminated"
            else "برای این قرارداد تکمیل‌شده صورت‌وضعیتی ثبت نشده است."
            if contract.status == "completed"
            else "برای شروع صورت‌وضعیت، نسخه تأییدشده شرایط قرارداد لازم است؛ وضعیت شرایط را بررسی کنید."
            if supports_terms and not approved_terms
            else "هنوز صورت‌وضعیتی ثبت نشده است؛ مبنا و اندازه‌گیری‌های لازم را در مسیر همین قرارداد بررسی کنید."
            if receivable
            else "هنوز گواهی پرداختی ثبت نشده است؛ اندازه‌گیری‌های تأییدشده پیمان جزء را بررسی کنید."
        ),
        "can_measurements": (
            payable
            and access(P.PAYABLE_MEASUREMENTS_VIEW)
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=P.PAYABLE_MEASUREMENTS_VIEW,
            )
        )
        or (receivable and access(P.PROGRESS_VIEW)),
        "measurement_url": reverse("billing:payable_measurement_list")
        if payable and route_exposed("billing:payable_measurement_list")
        else "#progress",
        "finalized_note": "قرارداد خاتمه‌یافته است؛ سوابق نهایی برای بازبینی حفظ شده‌اند."
        if contract.status == "terminated"
        else "اطلاعات پایه و ردیف‌های نهایی‌شده محفوظ‌اند؛ تاریخچه تغییرات مستقل نگهداری می‌شود."
        if not draft
        else "",
    }


@transaction.atomic
def submit_workspace_form(
    request: HttpRequest, contract: Contract, workspace: dict
) -> str | None:
    """Return a local redirect anchor, or let a bound form render its errors."""
    action = request.POST.get("detail_action", "")
    form = workspace["forms"].get(action)
    if form is None:
        raise PermissionDenied("این عملیات برای وضعیت قرارداد یا دسترسی شما مجاز نیست.")
    if not form.is_valid():
        return None
    try:
        contract = (
            Contract.objects.select_for_update(of=("self",))
            .select_related("project")
            .get(
                pk=contract.pk,
                organization=request.organization,
                deleted_at__isnull=True,
            )
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد در محدوده دسترسی فعلی نیست.") from exc
    # Scoped selectors can use DISTINCT for multiple grants; PostgreSQL cannot
    # combine that SELECT with FOR UPDATE. Lock the already-resolved tenant row,
    # then re-run the unchanged authenticated selector inside this transaction.
    if (
        not get_organization_contracts(
            user=request.user, organization=request.organization
        )
        .filter(pk=contract.pk)
        .exists()
    ):
        raise PermissionDenied("قرارداد در محدوده دسترسی فعلی نیست.")
    if action in ("edit_base", "add_item") and contract.status != "draft":
        raise PermissionDenied(
            "اطلاعات پایه و ردیف‌های قرارداد نهایی‌شده از این مسیر ویرایش نمی‌شوند."
        )
    if action == "create_term" and (
        contract.status not in ("draft", "active", "completed")
        or not (
            contract.direction == "receivable"
            or (
                contract.direction == "payable"
                and contract.contract_type == "subcontract"
            )
        )
    ):
        raise PermissionDenied(
            "تهیه نسخه شرایط برای این وضعیت و نوع قرارداد مجاز نیست."
        )
    data = form.cleaned_data
    common = {
        "organization": request.organization,
        "actor": request.user,
        "contract": contract,
    }
    if action == "edit_base":
        update_draft_contract(
            **common,
            title=data["title"],
            counterparty_name=data["counterparty_name"],
            party=data["party"],
            direction=data["direction"] or None,
            contract_type=data["contract_type"] or None,
            contract_value=data["contract_value"],
            notes=data["notes"],
        )
        return "information"
    if action == "add_item":
        add_contract_item(
            **common,
            description=data["description"],
            quantity=data["quantity"],
            unit_price=data["unit_price"],
            unit=data["unit_of_measure"].symbol,
            unit_of_measure=data["unit_of_measure"],
            sort_order=workspace["item_count"] + 1,
        )
        return "items"
    if action == "create_term":
        create_contract_term_version(**common, **data)
        return "terms"
    raise PermissionDenied("عملیات ناشناخته است.")


def present_workspace_dashboard(
    contract: Contract, workspace: dict, dashboard: dict
) -> None:
    """Choose relevant existing projections; never derive a business readiness gate."""
    amount = dashboard["kpis"][0]
    item_card = {
        "label": "ردیف‌های قرارداد",
        "value": workspace["item_count"],
        "unit": "ردیف",
        "tone": "value",
        "icon": "layers",
        "note": "ردیف‌های ثبت‌شده همین قرارداد",
    }
    term_card = {
        "label": "شرایط قرارداد",
        "text": workspace["term_status"],
        "tone": "remaining",
        "icon": "document",
        "note": "وضعیت نسخه‌های شرایط",
    }
    if workspace["is_draft"]:
        amount = {
            **amount,
            "label": "مبلغ قرارداد",
            "value": contract.contract_value,
            "note": "مبلغ ثبت‌شده در پیش‌نویس",
        }
        cards = [amount, item_card]
        if workspace["supports_terms"]:
            cards.append(term_card)
        cards.append(
            {
                "label": "آماده‌سازی اطلاعات",
                "text": workspace["readiness"][-1]["value"],
                "tone": "physical",
                "icon": "check",
                "note": "وضعیت آماده‌سازی؛ بدون تغییر وضعیت قرارداد",
            }
        )
        dashboard["kpis"] = cards
        dashboard["show_billing"] = False
        dashboard["show_baselines"] = False
    elif workspace["supports_operations"] and dashboard["show_billing"]:
        dashboard["kpis"] = [
            card for card in dashboard["kpis"] if card["value"] is not None
        ]
    else:
        dashboard["kpis"] = [amount, item_card] + (
            [term_card] if workspace["supports_terms"] else []
        )
    workspace["show_financial"] = (
        not workspace["is_draft"]
        and workspace["supports_operations"]
        and dashboard["show_billing"]
    )
    workspace["show_progress"] = (
        not workspace["is_draft"]
        and workspace["supports_operations"]
        and workspace["can_measurements"]
    )
    workspace["show_billing"] = (
        not workspace["is_draft"]
        and workspace["supports_operations"]
        and dashboard["show_billing"]
    )
