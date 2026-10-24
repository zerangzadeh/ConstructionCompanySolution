from __future__ import annotations

from uuid import uuid4

from django import forms

from apps.accounting.models import (
    Account,
    AccountType,
    FinancialStatementKind,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalStatus,
    ReconciliationExceptionDispositionCode,
)
from apps.organizations.models import Organization, OrganizationMembership
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite, WBSNode
from core.forms import JalaliDateMixin, attach_parent_choice_ui


class AccountingFormMixin:
    """Use only tenant-scoped choices; services remain the authority."""

    field_class = (
        "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
        "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
        "focus:ring-blue-100"
    )

    def _style_fields(self) -> None:
        for field in self.fields.values():
            field.widget.attrs["class"] = self.field_class


class AccountForm(AccountingFormMixin, forms.Form):
    code = forms.CharField(max_length=50, label="کد حساب")
    name = forms.CharField(max_length=255, label="نام حساب")
    account_type = forms.ChoiceField(choices=AccountType.choices, label="نوع حساب")
    parent = forms.ModelChoiceField(
        queryset=Account.objects.none(), required=False, label="حساب والد"
    )
    is_posting = forms.BooleanField(required=False, label="حساب قابل ثبت")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = Account.objects.filter(
            organization=organization, archived_at__isnull=True, is_posting=False
        )
        self._style_fields()


class FiscalYearForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    code = forms.CharField(max_length=30, label="کد سال مالی")
    name = forms.CharField(max_length=255, label="نام سال مالی")
    starts_on = forms.DateField(label="شروع سال")
    ends_on = forms.DateField(label="پایان سال")
    calendar_version = forms.IntegerField(min_value=1, initial=1, label="نسخه تقویم")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class FiscalPeriodForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(), label="سال مالی"
    )
    number = forms.IntegerField(min_value=1, label="شماره دوره")
    name = forms.CharField(max_length=255, label="نام دوره")
    starts_on = forms.DateField(label="شروع دوره")
    ends_on = forms.DateField(label="پایان دوره")
    is_adjustment = forms.BooleanField(required=False, label="دوره تعدیلی")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
            organization=organization
        )
        self._style_fields()


class JournalForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    period = forms.ModelChoiceField(
        queryset=FiscalPeriod.objects.none(), label="دوره مالی"
    )
    document_date = forms.DateField(label="تاریخ سند")
    accounting_date = forms.DateField(label="تاریخ حسابداری")
    description = forms.CharField(widget=forms.Textarea, label="شرح سند")
    source_key = forms.CharField(
        max_length=120, label="کلید منبع", widget=forms.HiddenInput, initial=uuid4
    )
    evidence_reference = forms.CharField(
        max_length=500, required=False, label="مرجع مدرک"
    )
    reconciliation_reference = forms.CharField(
        max_length=500, required=False, label="مرجع تطبیق"
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["period"].queryset = FiscalPeriod.objects.filter(
            organization=organization
        ).select_related("fiscal_year")
        self._style_fields()


class ReplacementJournalForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    period = forms.ModelChoiceField(
        queryset=FiscalPeriod.objects.none(), label="دوره مالی"
    )
    document_date = forms.DateField(label="تاریخ سند")
    accounting_date = forms.DateField(label="تاریخ حسابداری")
    description = forms.CharField(widget=forms.Textarea, label="شرح سند جایگزین")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["period"].queryset = FiscalPeriod.objects.filter(
            organization=organization
        ).select_related("fiscal_year")
        self._style_fields()


class JournalLineForm(AccountingFormMixin, forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), label="حساب")
    debit = forms.DecimalField(
        min_value=0,
        decimal_places=6,
        max_digits=24,
        required=False,
        initial=0,
        label="بدهکار",
    )
    credit = forms.DecimalField(
        min_value=0,
        decimal_places=6,
        max_digits=24,
        required=False,
        initial=0,
        label="بستانکار",
    )
    description = forms.CharField(max_length=500, required=False, label="شرح ردیف")
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(), required=False, label="پروژه"
    )
    site = forms.ModelChoiceField(
        queryset=ProjectSite.objects.none(), required=False, label="کارگاه"
    )
    wbs_node = forms.ModelChoiceField(
        queryset=WBSNode.objects.none(), required=False, label="WBS"
    )
    party = forms.ModelChoiceField(
        queryset=BusinessParty.objects.none(), required=False, label="طرف تجاری"
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(
            organization=organization, is_posting=True, archived_at__isnull=True
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            project__organization=organization
        )
        self.fields["wbs_node"].queryset = WBSNode.objects.filter(
            project__organization=organization
        )
        attach_parent_choice_ui(self, "site", "project", "project_id")
        attach_parent_choice_ui(self, "wbs_node", "project", "project_id")
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        )
        self._style_fields()

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        debit, credit = cleaned.get("debit") or 0, cleaned.get("credit") or 0
        if bool(debit) == bool(credit):
            raise forms.ValidationError("هر ردیف باید فقط بدهکار یا فقط بستانکار باشد.")
        return cleaned


class OpeningImportForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(), label="سال مالی"
    )
    period = forms.ModelChoiceField(
        queryset=FiscalPeriod.objects.none(), label="دوره افتتاحیه"
    )
    source_reference = forms.CharField(max_length=500, label="مرجع منبع")
    cutoff_date = forms.DateField(label="تاریخ برش")
    evidence_reference = forms.CharField(max_length=500, label="مرجع مدرک")
    reconciliation_reference = forms.CharField(max_length=500, label="مرجع تطبیق")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
            organization=organization
        )
        self.fields["period"].queryset = FiscalPeriod.objects.filter(
            organization=organization
        )
        attach_parent_choice_ui(self, "period", "fiscal_year", "fiscal_year_id")
        self._style_fields()


class ReasonForm(AccountingFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="دلیل")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class ProtectedReasonForm(ReasonForm):
    requested_by = forms.ModelChoiceField(
        queryset=OrganizationMembership.objects.none(), label="درخواست‌کننده مستقل"
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["requested_by"].queryset = OrganizationMembership.objects.filter(
            organization=organization
        )


class ReconciliationRunForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    cutoff_date = forms.DateField(label="تاریخ برش")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class DispositionForm(AccountingFormMixin, forms.Form):
    disposition = forms.ChoiceField(
        choices=ReconciliationExceptionDispositionCode.choices, label="نوع تعیین تکلیف"
    )
    reason = forms.CharField(widget=forms.Textarea, label="دلیل")
    evidence_reference = forms.CharField(
        max_length=500, required=False, label="مرجع مدرک"
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class StatementRunForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    kind = forms.ChoiceField(choices=FinancialStatementKind.choices, label="نوع گزارش")
    starts_on = forms.DateField(required=False, label="شروع بازه")
    ends_on = forms.DateField(label="پایان / تاریخ برش")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        starts_on = cleaned.get("starts_on")
        ends_on = cleaned.get("ends_on")
        if cleaned.get("kind") == FinancialStatementKind.PROFIT_LOSS and not starts_on:
            self.add_error("starts_on", "صورت سود و زیان به تاریخ شروع نیاز دارد.")
        if starts_on and ends_on and ends_on < starts_on:
            self.add_error("ends_on", "پایان بازه پیش از شروع آن است.")
        return cleaned


class ControlledAdjustmentForm(AccountingFormMixin, JalaliDateMixin, forms.Form):
    original = forms.ModelChoiceField(
        queryset=JournalEntry.objects.none(), label="سند قطعی دوره بسته"
    )
    period = forms.ModelChoiceField(
        queryset=FiscalPeriod.objects.none(), label="دوره تعدیلی باز"
    )
    document_date = forms.DateField(label="تاریخ سند")
    accounting_date = forms.DateField(label="تاریخ حسابداری")
    description = forms.CharField(widget=forms.Textarea, label="شرح تعدیل")
    source_key = forms.CharField(max_length=120, label="کلید منبع تعدیل")
    reason = forms.CharField(widget=forms.Textarea, label="دلیل تعدیل")
    evidence_reference = forms.CharField(max_length=500, label="مرجع مدرک")
    reconciliation_reference = forms.CharField(max_length=500, label="مرجع تطبیق")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["original"].queryset = JournalEntry.objects.filter(
            organization=organization,
            status=JournalStatus.POSTED,
            period__status="closed",
        ).select_related("period")
        self.fields["period"].queryset = FiscalPeriod.objects.filter(
            organization=organization,
            status="open",
            is_adjustment=True,
        ).select_related("fiscal_year")
        self._style_fields()
