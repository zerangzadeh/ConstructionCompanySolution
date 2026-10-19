"""Whitelisted native UI adapters; no generic state writer or domain workflow."""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode as P
from core.jalali import format_jalali

from . import operational_forms as forms
from . import services, statement_services
from .models import (
    AdvanceSettlement,
    BankStatementImport,
    ChequeInstrument,
    PaymentRequest,
    TreasuryAccount,
    TreasuryAdvance,
    TreasuryAdvanceReconciliationRun,
    TreasuryMovement,
)


@dataclass(frozen=True)
class Operation:
    title: str
    permission: str
    form: type
    service: object
    model: type | None = None
    argument: str = ""
    statuses: tuple[str, ...] = ()


def _transfer(**kwargs):
    return services.create_movement(kind="transfer", **kwargs)


def _preview_statement(*, file, **kwargs):
    from core.forms import parse_jalali_date

    source_bytes = file.read(65537)
    try:
        reader = csv.DictReader(
            io.StringIO(source_bytes.decode("utf-8-sig")), strict=True
        )
        if reader.fieldnames != [
            "transaction_date",
            "direction",
            "amount",
            "provider_row_id",
            "reference",
        ]:
            raise ValueError
        rows = []
        for index, row in enumerate(reader, 1):
            if (
                index > 1000
                or None in row
                or any(value is None for value in row.values())
            ):
                raise ValueError
            raw = row["transaction_date"]
            try:
                transaction_date = parse_jalali_date(raw)
            except ValueError:
                transaction_date = date.fromisoformat(raw)
            rows.append(
                statement_services.StatementRowInput(
                    row_number=index,
                    transaction_date=transaction_date,
                    direction=row["direction"],
                    amount=forms.money().clean(row["amount"]),
                    provider_row_id=row["provider_row_id"],
                    reference=row["reference"],
                )
            )
    except (UnicodeError, ValueError, InvalidOperation, csv.Error) as exc:
        raise ValidationError("ساختار، تاریخ یا مبلغ فایل CSV معتبر نیست.") from exc
    return statement_services.preview_statement_import(
        **kwargs,
        format_code="bonira_native_csv_v1",
        file_name=file.name,
        source_bytes=source_bytes,
        rows=rows,
        max_file_bytes=65536,
        max_rows=1000,
    )


# Each UI action names an existing service and existing business permission.
# No request-supplied service, field assignment, permission or state expression.
OPERATIONS = {
    "account_create": Operation(
        "حساب جدید",
        P.TREASURY_ACCOUNTS_MANAGE,
        forms.AccountCreateForm,
        services.create_treasury_account,
    ),
    "account_status": Operation(
        "تغییر وضعیت حساب",
        P.TREASURY_ACCOUNTS_MANAGE,
        forms.AccountTransitionForm,
        services.transition_treasury_account,
        TreasuryAccount,
        "account",
    ),
    "account_mapping": Operation(
        "نگاشت حسابداری حساب",
        P.TREASURY_MAPPINGS_MANAGE,
        forms.AccountMappingForm,
        services.create_account_mapping_version,
        TreasuryAccount,
        "account",
    ),
    "transfer": Operation(
        "انتقال بین حساب‌ها", P.TREASURY_MOVEMENTS_CREATE, forms.TransferForm, _transfer
    ),
    "request_create": Operation(
        "درخواست پرداخت یا تنخواه",
        P.TREASURY_PAYMENT_REQUESTS_CREATE,
        forms.RequestCreateForm,
        services.create_payment_request,
    ),
    "request_submit": Operation(
        "ارسال درخواست",
        P.TREASURY_PAYMENT_REQUESTS_SUBMIT,
        forms.ReasonForm,
        services.submit_payment_request,
        PaymentRequest,
        "request",
        ("draft",),
    ),
    "request_decide": Operation(
        "بررسی درخواست",
        P.TREASURY_PAYMENT_REQUESTS_APPROVE,
        forms.DecisionForm,
        services.decide_payment_request,
        PaymentRequest,
        "request",
        ("submitted",),
    ),
    "request_cancel": Operation(
        "لغو درخواست",
        P.TREASURY_PAYMENT_REQUESTS_CREATE,
        forms.ReasonForm,
        services.cancel_payment_request,
        PaymentRequest,
        "request",
        ("draft", "submitted", "approved"),
    ),
    "request_release": Operation(
        "اتصال پرداخت قطعی",
        P.TREASURY_PAYMENT_REQUESTS_RELEASE,
        forms.ReleaseForm,
        services.release_payment_request,
        PaymentRequest,
        "request",
        ("approved",),
    ),
    "advance_open": Operation(
        "بازکردن تنخواه پرداخت‌شده",
        P.TREASURY_ADVANCES_MANAGE,
        forms.OperationalForm,
        services.open_advance,
        PaymentRequest,
        "request",
        ("released",),
    ),
    "cheque_create": Operation(
        "چک جدید",
        P.TREASURY_CHEQUES_MANAGE,
        forms.ChequeCreateForm,
        services.create_cheque,
    ),
    "cheque_status": Operation(
        "گردش چک",
        P.TREASURY_CHEQUES_MANAGE,
        forms.ChequeTransitionForm,
        services.transition_cheque,
        ChequeInstrument,
        "cheque",
        ("draft", "received", "issued", "deposited", "delivered", "presented"),
    ),
    "cheque_clear": Operation(
        "وصول چک و ثبت قطعی",
        P.TREASURY_CHEQUES_CLEAR,
        forms.ChequeClearForm,
        services.clear_cheque,
        ChequeInstrument,
        "cheque",
        ("presented",),
    ),
    "cheque_bounce": Operation(
        "برگشت چک وصول‌شده",
        P.TREASURY_CHEQUES_CLEAR,
        forms.ReverseForm,
        services.bounce_cleared_cheque,
        ChequeInstrument,
        "cheque",
        ("cleared",),
    ),
    "advance_settle": Operation(
        "ثبت تسویه تنخواه",
        P.TREASURY_ADVANCES_SETTLE,
        forms.SettlementCreateForm,
        services.create_advance_settlement,
        TreasuryAdvance,
        "advance",
        ("open", "partially_settled"),
    ),
    "advance_reverse": Operation(
        "برگشت پرداخت تنخواه",
        P.TREASURY_ADVANCES_REVERSE,
        forms.ReverseForm,
        services.reverse_advance_issue,
        TreasuryAdvance,
        "advance",
        ("open", "partially_settled", "settled"),
    ),
    "settlement_submit": Operation(
        "ارسال تسویه",
        P.TREASURY_ADVANCES_SETTLE,
        forms.ReasonForm,
        services.submit_advance_settlement,
        AdvanceSettlement,
        "settlement",
        ("draft",),
    ),
    "settlement_decide": Operation(
        "بررسی تسویه",
        P.TREASURY_ADVANCES_SETTLE,
        forms.DecisionForm,
        services.decide_advance_settlement,
        AdvanceSettlement,
        "settlement",
        ("submitted",),
    ),
    "settlement_cancel": Operation(
        "لغو تسویه",
        P.TREASURY_ADVANCES_SETTLE,
        forms.ReasonForm,
        services.cancel_advance_settlement,
        AdvanceSettlement,
        "settlement",
        ("draft", "submitted"),
    ),
    "settlement_reverse": Operation(
        "برگشت تسویه",
        P.TREASURY_ADVANCES_REVERSE,
        forms.ReverseForm,
        services.reverse_advance_settlement,
        AdvanceSettlement,
        "settlement",
        ("approved",),
    ),
    "advance_reconcile": Operation(
        "تطبیق تنخواه",
        P.TREASURY_RECONCILIATIONS_RUN,
        forms.AdvanceReconcileForm,
        services.run_advance_reconciliation,
    ),
    "gl_reconcile": Operation(
        "تطبیق خزانه با دفترکل",
        P.TREASURY_RECONCILIATIONS_RUN,
        forms.GLReconcileForm,
        services.run_treasury_gl_reconciliation,
    ),
    "statement_preview": Operation(
        "پیش‌نمایش صورت‌حساب",
        P.TREASURY_STATEMENTS_IMPORT,
        forms.StatementPreviewForm,
        _preview_statement,
    ),
    "statement_accept": Operation(
        "پذیرش صورت‌حساب",
        P.TREASURY_STATEMENTS_ACCEPT,
        forms.ReasonForm,
        statement_services.accept_statement_import,
        BankStatementImport,
        "statement_import",
        ("previewed",),
    ),
}

SCOPES = {
    PaymentRequest: ("project_id", "site_id"),
    TreasuryAdvance: ("request__project_id", "request__site_id"),
    AdvanceSettlement: ("advance__request__project_id", "advance__request__site_id"),
}
RESOURCES = {
    "account": TreasuryAccount,
    "request": PaymentRequest,
    "cheque": ChequeInstrument,
    "advance": TreasuryAdvance,
    "settlement": AdvanceSettlement,
    "statement": BankStatementImport,
}


def _objects(model, request):
    queryset = model.objects.filter(organization=request.organization)
    if model in SCOPES:
        project, site = SCOPES[model]
        return scope_queryset(
            queryset,
            membership=get_active_membership(
                user=request.user, organization=request.organization
            ),
            project_lookup=project,
            site_lookup=site,
        )
    if not has_business_permission(
        user=request.user, organization=request.organization, permission=P.TREASURY_VIEW
    ):
        return queryset.none()
    return queryset


def _allowed(request, operation, target=None):
    project = site = None
    scoped = target
    if isinstance(scoped, AdvanceSettlement):
        scoped = scoped.advance.request
    elif isinstance(scoped, TreasuryAdvance):
        scoped = scoped.request
    if isinstance(scoped, PaymentRequest):
        project, site = scoped.project, scoped.site
    return has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=operation.permission,
        project=project,
        site=site,
        allow_any_scope=target is None,
    )


def _summary(target):
    """Display the authorized source being reviewed; never derive a balance."""
    if target is None:
        return []
    rows = [("شناسه مرجع", str(target.pk)), ("وضعیت", target.get_status_display())]
    source = target
    if isinstance(target, TreasuryAdvance):
        source = target.request
    elif isinstance(target, AdvanceSettlement):
        source = target.advance.request
    if isinstance(source, PaymentRequest):
        rows += [
            ("نوع درخواست", source.get_kind_display()),
            ("شرح", source.purpose),
            ("مبلغ درخواست (ریال)", source.amount),
            ("طرف تجاری", source.party or "—"),
            ("کارمند ذی‌نفع", source.employee or "—"),
            ("پروژه", source.project or "—"),
            ("کارگاه", source.site or "—"),
        ]
    if isinstance(target, AdvanceSettlement):
        rows += [("مبلغ تسویه (ریال)", target.amount)]
    if isinstance(target, TreasuryAccount):
        rows += [("حساب", target.name), ("کد", target.code)]
    if isinstance(target, ChequeInstrument):
        rows += [
            ("جهت", target.get_direction_display()),
            ("مبلغ (ریال)", target.amount),
            ("حساب", target.controlled_account.name),
            ("سررسید", format_jalali(target.due_date)),
            ("سریال پوشیده", "••••" + target.serial_last4),
            ("طرف تجاری", target.party or "—"),
        ]
    if isinstance(target, BankStatementImport):
        rows += [
            ("حساب", target.account.name),
            ("فایل منبع", target.file_name),
            ("ابتدای بازه", format_jalali(target.period_start)),
            ("انتهای بازه", format_jalali(target.period_end)),
            ("تعداد ردیف", target.row_count),
        ]
    return rows


@active_organization_required
@organization_permission_required(P.TREASURY_VIEW)
@require_GET
def workspace(request):
    creation = [
        {"title": op.title, "url": reverse("treasury:operation", args=[name])}
        for name, op in OPERATIONS.items()
        if op.model is None and _allowed(request, op)
    ]
    groups = []
    for model, title in [
        (TreasuryAccount, "حساب‌ها"),
        (PaymentRequest, "درخواست‌ها"),
        (ChequeInstrument, "چک‌ها"),
        (TreasuryAdvance, "تنخواه‌ها"),
        (AdvanceSettlement, "تسویه‌های تنخواه"),
        (BankStatementImport, "صورت‌حساب‌ها"),
    ]:
        rows = []
        page_key = model._meta.model_name + "_page"
        page = Paginator(
            _objects(model, request).order_by("-created_at", "pk"), 25
        ).get_page(request.GET.get(page_key))
        for item in page:
            actions = []
            for name, op in OPERATIONS.items():
                if op.model is not model or not _allowed(request, op, item):
                    continue
                if op.statuses and item.status not in op.statuses:
                    continue
                if name == "advance_open" and item.kind not in {
                    "employee_advance",
                    "vendor_advance",
                }:
                    continue
                actions.append(
                    {
                        "title": op.title,
                        "url": reverse(
                            "treasury:object_operation", args=[name, item.pk]
                        ),
                    }
                )
            label = getattr(item, "name", "")
            if not label:
                display = getattr(item, "get_kind_display", None) or getattr(
                    item, "get_direction_display", None
                )
                label = display() if display else title
            resource = next(key for key, value in RESOURCES.items() if value is model)
            rows.append(
                {
                    "object": item,
                    "title": label,
                    "actions": actions,
                    "detail_url": reverse(
                        "treasury:operational_detail", args=[resource, item.pk]
                    ),
                }
            )
        links = {}
        for direction, number in [
            ("previous", page.previous_page_number() if page.has_previous() else None),
            ("next", page.next_page_number() if page.has_next() else None),
        ]:
            if number:
                query = request.GET.copy()
                query[page_key] = str(number)
                links[direction] = "?" + query.urlencode()
        groups.append({"title": title, "rows": rows, "links": links})
    advance_runs = (
        TreasuryAdvanceReconciliationRun.objects.filter(
            organization=request.organization
        ).order_by("-created_at")[:20]
        if has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=P.TREASURY_VIEW,
        )
        else []
    )
    return render(
        request,
        "treasury/operations.html",
        {"creation": creation, "groups": groups, "advance_runs": advance_runs},
    )


@active_organization_required
@organization_permission_required(P.TREASURY_VIEW)
@require_GET
def detail(request, resource, object_id):
    model = RESOURCES.get(resource)
    if model is None:
        raise Http404
    target = get_object_or_404(_objects(model, request), pk=object_id)
    return render(
        request, "treasury/operational_detail.html", {"summary": _summary(target)}
    )


@active_organization_required
@organization_permission_required(P.TREASURY_VIEW)
@require_http_methods(["GET", "POST"])
def operation(request, operation, object_id=None):
    op = OPERATIONS.get(operation)
    if op is None or (op.model is None) != (object_id is None):
        raise Http404
    require_organization_permission(request, op.permission)
    target = (
        get_object_or_404(_objects(op.model, request), pk=object_id)
        if op.model
        else None
    )
    if not _allowed(request, op, target):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    kwargs = {
        "organization": request.organization,
        "actor": request.user,
        "target": target,
    }
    form = op.form(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        **kwargs,
    )
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        if op.argument:
            values[op.argument] = target
        try:
            result = op.service(
                organization=request.organization, actor=request.user, **values
            )
        except ValidationError as exc:
            form.add_error(None, ValidationError(exc.messages))
        else:
            messages.success(request, "عملیات خزانه‌داری با حفظ سابقه ثبت شد.")
            if isinstance(result, TreasuryMovement):
                return redirect("treasury:movement_detail", movement_id=result.pk)
            return redirect("treasury:operations")
    return render(
        request,
        "treasury/operation_form.html",
        {
            "form": form,
            "title": op.title,
            "target": target,
            "summary": _summary(target),
        },
    )
