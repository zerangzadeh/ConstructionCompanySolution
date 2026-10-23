from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import OuterRef, Subquery, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounting.forms import (
    AccountForm,
    ControlledAdjustmentForm,
    DispositionForm,
    FiscalPeriodForm,
    FiscalYearForm,
    JournalForm,
    JournalLineForm,
    OpeningImportForm,
    ProtectedReasonForm,
    ReasonForm,
    ReconciliationRunForm,
    ReplacementJournalForm,
    StatementRunForm,
)
from apps.accounting.models import (
    Account,
    FinancialStatementRun,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalKind,
    JournalLine,
    JournalStatus,
    OpeningBalanceImport,
    ReconciliationExceptionSnapshot,
    ReconciliationRun,
)
from apps.accounting.reconciliation import (
    create_manual_opening_reconciliation_run,
    dispose_reconciliation_exception,
    sign_off_reconciliation_run,
)
from apps.accounting.reporting import build_statement, retain_statement
from apps.accounting.services import (
    accept_opening_import,
    add_journal_line,
    add_opening_import_line,
    close_period,
    create_account,
    create_controlled_adjustment,
    create_fiscal_period,
    create_fiscal_year,
    create_journal,
    create_opening_import,
    create_replacement_journal,
    list_accounts,
    post_journal,
    reopen_period,
    reverse_journal,
    submit_journal,
    submit_opening_import,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import paginate_table


def _form_error(form: object, exc: Exception) -> None:
    form.add_error(None, str(exc))  # type: ignore[attr-defined]


def _tenant_object(model: object, organization: object, pk: str) -> object:
    return get_object_or_404(model, pk=pk, organization=organization)


@dataclass
class AccountTreeNode:
    """Presentation-only node for the chart-of-accounts tree."""

    account: Account
    depth: int
    children: list[AccountTreeNode] = field(default_factory=list)


def _build_account_tree(accounts: list[Account]) -> list[AccountTreeNode]:
    """Keep the service-owned account list intact while arranging it for display."""

    account_ids = {account.pk for account in accounts}
    children_by_parent: dict[UUID, list[Account]] = {}
    for account in accounts:
        if account.parent_id in account_ids:
            children_by_parent.setdefault(account.parent_id, []).append(account)

    rendered_account_ids: set[UUID] = set()

    def build_node(
        account: Account, *, depth: int, ancestors: frozenset[UUID]
    ) -> AccountTreeNode:
        rendered_account_ids.add(account.pk)
        child_ancestors = ancestors | {account.pk}
        return AccountTreeNode(
            account=account,
            depth=depth,
            children=[
                build_node(child, depth=depth + 1, ancestors=child_ancestors)
                for child in children_by_parent.get(account.pk, [])
                if child.pk not in child_ancestors
            ],
        )

    roots = [
        account
        for account in accounts
        if account.parent_id is None or account.parent_id not in account_ids
    ]
    tree = [build_node(account, depth=0, ancestors=frozenset()) for account in roots]

    # Keep every account visible if legacy data ever contains a parent cycle.
    tree.extend(
        build_node(account, depth=0, ancestors=frozenset())
        for account in accounts
        if account.pk not in rendered_account_ids
    )
    return tree


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    return render(
        request,
        "accounting/dashboard.html",
        {
            "account_count": Account.objects.filter(organization=organization).count(),
            "open_period_count": FiscalPeriod.objects.filter(
                organization=organization, status="open"
            ).count(),
            "proposed_count": JournalEntry.objects.filter(
                organization=organization, status=JournalStatus.PROPOSED
            ).count(),
            "recent_journals": JournalEntry.objects.filter(organization=organization)
            .select_related("period")
            .order_by("-created_at")[:8],
            "statement_count": FinancialStatementRun.objects.filter(
                organization=organization
            ).count(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = list(
        list_accounts(organization=request.organization, actor=request.user)
    )
    return render(
        request,
        "accounting/account_list.html",
        {
            "accounts": accounts,
            "account_tree": _build_account_tree(accounts),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_ACCOUNTS_MANAGE)
def account_create(request: HttpRequest) -> HttpResponse:
    form = AccountForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_account(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            messages.success(request, "حساب با ثبت ممیزی‌شده ایجاد شد.")
            return redirect("accounting:account_list")
    return render(
        request, "accounting/form.html", {"form": form, "title": "ایجاد حساب"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def period_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounting/period_list.html",
        {
            "years": FiscalYear.objects.filter(
                organization=request.organization
            ).prefetch_related("periods"),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE)
def fiscal_year_create(request: HttpRequest) -> HttpResponse:
    form = FiscalYearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_fiscal_year(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            return redirect("accounting:period_list")
    return render(
        request, "accounting/form.html", {"form": form, "title": "ایجاد سال مالی"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE)
def fiscal_period_create(request: HttpRequest) -> HttpResponse:
    form = FiscalPeriodForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            create_fiscal_period(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            return redirect("accounting:period_list")
    return render(
        request, "accounting/form.html", {"form": form, "title": "ایجاد دوره مالی"}
    )


def _period_protected_action(
    request: HttpRequest, period_id: str, *, reopen: bool
) -> HttpResponse:
    period = _tenant_object(FiscalPeriod, request.organization, period_id)
    form = ProtectedReasonForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            service = reopen_period if reopen else close_period
            service(
                organization=request.organization,
                actor=request.user,
                period=period,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            messages.success(request, "دوره مالی با کنترل تفکیک وظایف به‌روزرسانی شد.")
            return redirect("accounting:period_list")
    return render(
        request,
        "accounting/form.html",
        {
            "form": form,
            "title": "بازگشایی دوره مالی" if reopen else "بستن دوره مالی",
            "back_url": "accounting:period_list",
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE)
def period_close(request: HttpRequest, period_id: str) -> HttpResponse:
    return _period_protected_action(request, period_id, reopen=False)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN)
def period_reopen(request: HttpRequest, period_id: str) -> HttpResponse:
    return _period_protected_action(request, period_id, reopen=True)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def journal_list(request: HttpRequest) -> HttpResponse:
    # Preserve the first-line debit display without loading whole line collections.
    journals = JournalEntry.objects.filter(organization=request.organization).annotate(
        list_debit=Subquery(
            JournalLine.objects.filter(
                organization=request.organization, journal_id=OuterRef("pk")
            )
            .order_by("line_number")
            .values("debit")[:1]
        )
    )
    page = paginate_table(
        journals,
        request,
        sort_fields={},
        default_ordering=("-accounting_date", "-created_at", "-pk"),
        per_page=25,
    )
    return render(
        request,
        "accounting/journal_list.html",
        {
            "journals": page.object_list,
            "page_obj": page,
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
def journal_create(request: HttpRequest) -> HttpResponse:
    form = JournalForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            journal = create_journal(
                organization=request.organization,
                actor=request.user,
                kind=JournalKind.MANUAL,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            return redirect("accounting:journal_detail", journal_id=journal.pk)
    return render(
        request, "accounting/form.html", {"form": form, "title": "ایجاد سند دستی"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def journal_detail(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(
        JournalEntry.objects.select_related(
            "period",
            "prepared_by__user",
            "submitted_by__user",
            "posted_by__user",
            "reverses",
            "replaces",
        ),
        request.organization,
        journal_id,
    )
    return render(
        request,
        "accounting/journal_detail.html",
        {
            "journal": journal,
            "lines": journal.lines.select_related(
                "account", "project", "site", "wbs_node", "party"
            ),
            "totals": journal.lines.aggregate(debit=Sum("debit"), credit=Sum("credit")),
            "line_form": JournalLineForm(organization=request.organization),
            "reason_form": ReasonForm(),
            "protected_reason_form": ProtectedReasonForm(
                organization=request.organization
            ),
            "replacement_form": ReplacementJournalForm(
                organization=request.organization
            ),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
@require_POST
def journal_line_add(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(JournalEntry, request.organization, journal_id)
    form = JournalLineForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            add_journal_line(
                organization=request.organization,
                actor=request.user,
                journal=journal,
                line_number=journal.lines.count() + 1,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
    if form.errors:
        return render(
            request,
            "accounting/journal_detail.html",
            {
                "journal": journal,
                "lines": journal.lines.select_related("account"),
                "totals": journal.lines.aggregate(
                    debit=Sum("debit"), credit=Sum("credit")
                ),
                "line_form": form,
                "reason_form": ReasonForm(),
                "protected_reason_form": ProtectedReasonForm(
                    organization=request.organization
                ),
                "replacement_form": ReplacementJournalForm(
                    organization=request.organization
                ),
            },
            status=400,
        )
    return redirect("accounting:journal_detail", journal_id=journal.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT)
@require_POST
def journal_submit(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(JournalEntry, request.organization, journal_id)
    try:
        submit_journal(
            organization=request.organization, actor=request.user, journal=journal
        )
        messages.success(request, "سند برای تأیید مستقل ارسال شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("accounting:journal_detail", journal_id=journal.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
@require_POST
def journal_post(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(JournalEntry, request.organization, journal_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            post_journal(
                organization=request.organization,
                actor=request.user,
                journal=journal,
                **form.cleaned_data,
            )
            messages.success(request, "سند قطعی و تغییرناپذیر ثبت شد.")
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل ثبت قطعی الزامی است.")
    return redirect("accounting:journal_detail", journal_id=journal.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
@require_POST
def journal_reverse(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(JournalEntry, request.organization, journal_id)
    form = ProtectedReasonForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            reversal = reverse_journal(
                organization=request.organization,
                actor=request.user,
                original=journal,
                accounting_date=journal.period.ends_on,
                period=journal.period,
                **form.cleaned_data,
            )
            return redirect("accounting:journal_detail", journal_id=reversal.pk)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "درخواست‌کننده مستقل و دلیل الزامی است.")
    return redirect("accounting:journal_detail", journal_id=journal.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
@require_POST
def journal_replacement(request: HttpRequest, journal_id: str) -> HttpResponse:
    original = _tenant_object(JournalEntry, request.organization, journal_id)
    form = ReplacementJournalForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            journal = create_replacement_journal(
                organization=request.organization,
                actor=request.user,
                original=original,
                **form.cleaned_data,
            )
            return redirect("accounting:journal_detail", journal_id=journal.pk)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "اطلاعات سند جایگزین معتبر نیست.")
    return redirect("accounting:journal_detail", journal_id=original.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def journal_source(request: HttpRequest, journal_id: str) -> HttpResponse:
    journal = _tenant_object(JournalEntry, request.organization, journal_id)
    opening = (
        OpeningBalanceImport.objects.filter(
            organization=request.organization, accepted_journal=journal
        )
        .prefetch_related("lines__account")
        .first()
    )
    return render(
        request,
        "accounting/source_detail.html",
        {
            "journal": journal,
            "opening": opening,
            "source_lines": opening.lines.select_related("account") if opening else (),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def opening_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounting/opening_list.html",
        {
            "openings": OpeningBalanceImport.objects.filter(
                organization=request.organization
            ).select_related("period", "prepared_by__user", "accepted_journal")
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
def opening_create(request: HttpRequest) -> HttpResponse:
    form = OpeningImportForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            opening = create_opening_import(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            return redirect("accounting:opening_detail", opening_id=opening.pk)
    return render(
        request, "accounting/form.html", {"form": form, "title": "ورودی مانده افتتاحیه"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def opening_detail(request: HttpRequest, opening_id: str) -> HttpResponse:
    opening = _tenant_object(
        OpeningBalanceImport.objects.select_related(
            "period", "prepared_by__user", "accepted_journal"
        ),
        request.organization,
        opening_id,
    )
    return render(
        request,
        "accounting/opening_detail.html",
        {
            "opening": opening,
            "lines": opening.lines.select_related("account"),
            "line_form": JournalLineForm(organization=request.organization),
            "reason_form": ReasonForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE)
@require_POST
def opening_line_add(request: HttpRequest, opening_id: str) -> HttpResponse:
    opening = _tenant_object(OpeningBalanceImport, request.organization, opening_id)
    form = JournalLineForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            add_opening_import_line(
                organization=request.organization,
                actor=request.user,
                opening_import=opening,
                line_number=opening.lines.count() + 1,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "ردیف افتتاحیه معتبر نیست.")
    return redirect("accounting:opening_detail", opening_id=opening.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT)
@require_POST
def opening_submit(request: HttpRequest, opening_id: str) -> HttpResponse:
    opening = _tenant_object(OpeningBalanceImport, request.organization, opening_id)
    try:
        submit_opening_import(
            organization=request.organization,
            actor=request.user,
            opening_import=opening,
        )
        messages.success(request, "ورودی افتتاحیه برای پذیرش مستقل ارسال شد.")
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("accounting:opening_detail", opening_id=opening.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_JOURNALS_POST)
@require_POST
def opening_accept(request: HttpRequest, opening_id: str) -> HttpResponse:
    opening = _tenant_object(OpeningBalanceImport, request.organization, opening_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            journal = accept_opening_import(
                organization=request.organization,
                actor=request.user,
                opening_import=opening,
                **form.cleaned_data,
            )
            return redirect("accounting:journal_detail", journal_id=journal.pk)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "دلیل پذیرش الزامی است.")
    return redirect("accounting:opening_detail", opening_id=opening.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def reconciliation_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounting/reconciliation_list.html",
        {
            "runs": ReconciliationRun.objects.filter(
                organization=request.organization
            ).select_related("created_by__user"),
            "run_form": ReconciliationRunForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_RUN)
@require_POST
def reconciliation_run(request: HttpRequest) -> HttpResponse:
    form = ReconciliationRunForm(request.POST)
    if form.is_valid():
        try:
            run = create_manual_opening_reconciliation_run(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
            return redirect("accounting:reconciliation_detail", run_id=run.pk)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "تاریخ برش معتبر نیست.")
    return redirect("accounting:reconciliation_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_VIEW)
@require_GET
def reconciliation_detail(request: HttpRequest, run_id: str) -> HttpResponse:
    run = _tenant_object(
        ReconciliationRun.objects.select_related("created_by__user"),
        request.organization,
        run_id,
    )
    return render(
        request,
        "accounting/reconciliation_detail.html",
        {
            "run": run,
            "exceptions": run.exceptions.select_related("disposition"),
            "tie_outs": run.tie_outs.all(),
            "disposition_form": DispositionForm(),
            "reason_form": ReasonForm(),
        },
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_DISPOSE
)
@require_POST
def reconciliation_dispose(request: HttpRequest, exception_id: str) -> HttpResponse:
    exception = _tenant_object(
        ReconciliationExceptionSnapshot.objects.select_related("run"),
        request.organization,
        exception_id,
    )
    form = DispositionForm(request.POST)
    if form.is_valid():
        try:
            dispose_reconciliation_exception(
                organization=request.organization,
                actor=request.user,
                exception=exception,
                **form.cleaned_data,
            )
            messages.success(request, "تعیین تکلیف تغییرناپذیر ثبت شد.")
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    return redirect("accounting:reconciliation_detail", run_id=exception.run_id)


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_SIGN_OFF
)
@require_POST
def reconciliation_sign_off(request: HttpRequest, run_id: str) -> HttpResponse:
    run = _tenant_object(ReconciliationRun, request.organization, run_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            sign_off_reconciliation_run(
                organization=request.organization,
                actor=request.user,
                run=run,
                **form.cleaned_data,
            )
            messages.success(request, "تأیید مستقل و محافظت‌شده ثبت شد.")
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    return redirect("accounting:reconciliation_detail", run_id=run.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW)
@require_GET
def statement_list(request: HttpRequest) -> HttpResponse:
    form = StatementRunForm(request.GET or None)
    preview = None
    if form.is_bound and form.is_valid():
        try:
            preview = build_statement(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
    return render(
        request,
        "accounting/statement_list.html",
        {
            "form": form,
            "preview": preview,
            "runs": FinancialStatementRun.objects.filter(
                organization=request.organization
            ).select_related("created_by__user")[:50],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_STATEMENTS_RUN)
@require_POST
def statement_run(request: HttpRequest) -> HttpResponse:
    form = StatementRunForm(request.POST)
    if form.is_valid():
        try:
            run = retain_statement(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, "نسخه تغییرناپذیر گزارش مالی نگهداری شد.")
            return redirect("accounting:statement_detail", run_id=run.pk)
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "پارامترهای گزارش مالی معتبر نیست.")
    return redirect("accounting:statement_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW)
@require_GET
def statement_detail(request: HttpRequest, run_id: str) -> HttpResponse:
    run = _tenant_object(
        FinancialStatementRun.objects.select_related("created_by__user"),
        request.organization,
        run_id,
    )
    return render(
        request,
        "accounting/statement_detail.html",
        {"run": run, "lines": run.lines.select_related("account")},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW)
@require_GET
def statement_account_ledger(
    request: HttpRequest, run_id: str, line_id: str
) -> HttpResponse:
    run = _tenant_object(FinancialStatementRun, request.organization, run_id)
    line = get_object_or_404(
        run.lines.select_related("account"),
        pk=line_id,
        organization=request.organization,
    )
    source_ids = [item["line"] for item in line.source_line_evidence]
    source_lines = (
        line.account.journal_lines.filter(
            organization=request.organization,
            pk__in=source_ids,
            journal__status=JournalStatus.POSTED,
        )
        .select_related("journal")
        .order_by("journal__accounting_date", "journal__number", "line_number")
    )
    return render(
        request,
        "accounting/statement_account_ledger.html",
        {"run": run, "statement_line": line, "source_lines": source_lines},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.ACCOUNTING_ADJUSTMENTS_PREPARE)
def controlled_adjustment_create(request: HttpRequest) -> HttpResponse:
    form = ControlledAdjustmentForm(
        request.POST or None, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        try:
            journal = create_controlled_adjustment(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            _form_error(form, exc)
        else:
            messages.success(
                request,
                "پیش‌نویس تعدیل با پیوند به سابقه قطعی ایجاد شد؛ ثبت آن مستقل است.",
            )
            return redirect("accounting:journal_detail", journal_id=journal.pk)
    return render(
        request,
        "accounting/form.html",
        {
            "form": form,
            "title": "ایجاد تعدیل کنترل‌شده",
            "back_url": "accounting:journal_list",
        },
    )
