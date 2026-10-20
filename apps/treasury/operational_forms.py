"""Native Treasury forms. All mutations remain owned by existing services."""

from decimal import Decimal
from uuid import uuid4

from django import forms

from apps.accounting.models import Account, FiscalPeriod
from apps.expenses.models import Expense
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import OrganizationMembership
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import Employee
from core.forms import JalaliDateMixin
from core.jalali import format_jalali

from .models import (
    ChequeDirection,
    ChequeStatus,
    PaymentRequestKind,
    TreasuryAccount,
    TreasuryAccountKind,
    TreasuryAccountStatus,
    TreasuryMovement,
)


class OperationalForm(JalaliDateMixin, forms.Form):
    def __init__(self, *args, organization, actor, target=None, **kwargs):
        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=actor, organization=organization)
        for field in self.fields.values():
            if not isinstance(field, forms.ModelChoiceField):
                continue
            model = field.queryset.model
            queryset = model.objects.filter(organization=organization)
            lookup = {
                Project: "pk",
                ProjectSite: "project_id",
                TreasuryMovement: "project_id",
                Expense: "project_id",
            }.get(model)
            if lookup:
                queryset = scope_queryset(
                    queryset,
                    membership=membership,
                    project_lookup=lookup,
                    site_lookup="pk"
                    if model is ProjectSite
                    else "site_id"
                    if model is TreasuryMovement
                    else None,
                )
            if model is OrganizationMembership:
                queryset = queryset.filter(status="active").select_related("user")
            if model is Expense:
                queryset = queryset.filter(status="approved", classification="direct")
                if not has_business_permission(
                    user=actor,
                    organization=organization,
                    permission=P.EXPENSES_VIEW,
                    allow_any_scope=True,
                ):
                    queryset = queryset.none()
            field.queryset = queryset
            if model is TreasuryAccount:
                field.label_from_instance = lambda item: f"{item.code} · {item.name}"
            elif model is TreasuryMovement:
                field.label_from_instance = lambda item: (
                    f"{item.get_kind_display()} · {item.amount} ریال · {format_jalali(item.movement_date)}"
                )
            elif model is OrganizationMembership:
                field.label_from_instance = lambda item: (
                    item.user.get_full_name() or item.user.username
                )
            elif model is FiscalPeriod:
                field.label_from_instance = lambda item: item.name


def choice(model, label, *, required=True):
    return forms.ModelChoiceField(
        queryset=model.objects.none(), label=label, required=required
    )


def money():
    return forms.DecimalField(
        label="مبلغ (ریال)",
        max_digits=24,
        decimal_places=6,
        min_value=Decimal("0.000001"),
    )


def reason():
    return forms.CharField(
        label="دلیل", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )


def key():
    return forms.CharField(widget=forms.HiddenInput, initial=uuid4, max_length=120)


class AccountCreateForm(OperationalForm):
    code = forms.CharField(label="کد حساب", max_length=50)
    name = forms.CharField(label="نام حساب", max_length=200)
    kind = forms.ChoiceField(label="نوع حساب", choices=TreasuryAccountKind.choices)
    sensitive_identifier = forms.CharField(
        label="شناسه بانکی محرمانه",
        required=False,
        max_length=100,
        widget=forms.PasswordInput,
    )
    custodian = choice(OrganizationMembership, "متولی", required=False)


class AccountTransitionForm(OperationalForm):
    to_status = forms.ChoiceField(
        label="وضعیت مقصد", choices=TreasuryAccountStatus.choices
    )
    requested_by = choice(OrganizationMembership, "درخواست‌کننده مستقل", required=False)
    reason = reason()


class AccountMappingForm(OperationalForm):
    cash_ledger_account = choice(Account, "حساب نقد دفترکل")
    clearing_ledger_account = choice(Account, "حساب واسط دفترکل")
    effective_from = forms.DateField(label="تاریخ شروع اعتبار")
    requested_by = choice(OrganizationMembership, "درخواست‌کننده مستقل", required=False)
    reason = reason()


class TransferForm(OperationalForm):
    source_account = choice(TreasuryAccount, "حساب مبدأ")
    destination_account = choice(TreasuryAccount, "حساب مقصد")
    project = choice(Project, "پروژه", required=False)
    site = choice(ProjectSite, "کارگاه", required=False)
    movement_date = forms.DateField(label="تاریخ انتقال")
    amount = money()
    description = forms.CharField(label="شرح", max_length=500)
    idempotency_key = key()


class RequestCreateForm(OperationalForm):
    kind = forms.ChoiceField(
        label="نوع درخواست",
        choices=[
            pair
            for pair in PaymentRequestKind.choices
            if pair[0] != PaymentRequestKind.PAYROLL
        ],
    )
    amount = money()
    purpose = forms.CharField(label="شرح درخواست", max_length=500)
    employee = choice(Employee, "کارمند ذی‌نفع", required=False)
    party = choice(BusinessParty, "طرف تجاری", required=False)
    project = choice(Project, "پروژه", required=False)
    site = choice(ProjectSite, "کارگاه", required=False)
    source_expense = choice(Expense, "هزینه مصوب بازپرداخت", required=False)
    idempotency_key = key()


class ReasonForm(OperationalForm):
    reason = reason()


class DecisionForm(ReasonForm):
    approve = forms.TypedChoiceField(
        label="تصمیم",
        choices=(("yes", "تأیید"), ("no", "رد")),
        coerce=lambda value: value == "yes",
    )


class ReleaseForm(ReasonForm):
    movement = choice(TreasuryMovement, "حرکت پرداخت قطعی")


class ChequeCreateForm(OperationalForm):
    direction = forms.ChoiceField(label="جهت چک", choices=ChequeDirection.choices)
    controlled_account = choice(TreasuryAccount, "حساب بانکی")
    amount = money()
    due_date = forms.DateField(label="سررسید")
    serial = forms.CharField(
        label="سریال چک", max_length=100, widget=forms.PasswordInput
    )
    party = choice(BusinessParty, "طرف تجاری", required=False)
    custodian = choice(OrganizationMembership, "متولی", required=False)


class ChequeTransitionForm(ReasonForm):
    to_status = forms.ChoiceField(label="وضعیت مقصد", choices=ChequeStatus.choices)

    def __init__(self, *args, target=None, **kwargs):
        super().__init__(*args, **kwargs)
        if target:
            from .services import _CHEQUE_TRANSITIONS

            allowed = _CHEQUE_TRANSITIONS.get(target.direction, {}).get(
                target.status, set()
            ) - {ChequeStatus.CLEARED}
            self.fields["to_status"].choices = [
                (value, label)
                for value, label in ChequeStatus.choices
                if value in allowed
            ]


class ChequeClearForm(ReasonForm):
    accounting_preparer = choice(OrganizationMembership, "تهیه‌کننده مستقل حسابداری")
    period = choice(FiscalPeriod, "دوره مالی")
    clearing_date = forms.DateField(label="تاریخ وصول")


class ReverseForm(ReasonForm):
    requested_by = choice(OrganizationMembership, "درخواست‌کننده مستقل برگشت")
    period = choice(FiscalPeriod, "دوره مالی")
    accounting_date = forms.DateField(label="تاریخ برگشت")


class SettlementCreateForm(OperationalForm):
    receipt_movement = choice(TreasuryMovement, "حرکت دریافت قطعی")
    amount = money()
    idempotency_key = key()


class AdvanceReconcileForm(OperationalForm):
    cutoff_date = forms.DateField(label="تاریخ مبنای تطبیق")
    idempotency_key = key()


class GLReconcileForm(OperationalForm):
    cutoff_date = forms.DateField(label="تاریخ مبنای تطبیق")


class StatementPreviewForm(OperationalForm):
    account = choice(TreasuryAccount, "حساب بانکی")
    provider_code = forms.CharField(label="مرجع ارائه‌دهنده صورت‌حساب", max_length=80)
    period_start = forms.DateField(label="ابتدای بازه")
    period_end = forms.DateField(label="انتهای بازه")
    file = forms.FileField(
        label="فایل CSV",
        help_text="فایل UTF-8 تا ۶۴ کیلوبایت و ۱۰۰۰ ردیف؛ ستون‌های transaction_date، direction، amount، provider_row_id و reference با جهت in یا out. تاریخ شمسی یا ISO پذیرفته می‌شود.",
    )
    idempotency_key = key()

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".csv") or upload.size > 65536:
            raise forms.ValidationError("فایل CSV تا ۶۴ کیلوبایت لازم است.")
        return upload
