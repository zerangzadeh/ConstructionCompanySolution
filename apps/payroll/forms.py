from __future__ import annotations

import json

from django import forms

from apps.organizations.models import PlatformPolicyVersion
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
)
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import Employee

from .models import (
    AdjustmentKind,
    CalculationMethod,
    ComponentKind,
    FinancialHandoffFamily,
    NetEffect,
    PayModel,
    PayrollComponent,
    PayrollInputSource,
    PayrollPeriod,
    PayrollRule,
    PayrollRun,
    PayrollRunKind,
    RateSource,
    StatutoryCalculation,
    StatutoryCalculationKind,
    StatutoryExportStatus,
    StatutoryIdentityEvidence,
    StatutoryOutput,
    StatutoryRecordKind,
    StatutoryResolutionAction,
    StatutoryReviewDisposition,
)


class OrganizationForm(forms.Form):
    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization


class FinancialHandoffPrepareForm(OrganizationForm):
    run = forms.ModelChoiceField(
        queryset=PayrollRun.objects.none(), label="اجرای قطعی حقوق"
    )
    family = forms.ChoiceField(
        choices=FinancialHandoffFamily.choices, label="خانواده تحویل"
    )
    idempotency_key = forms.CharField(max_length=120, label="کلید تکرارناپذیری")
    proposed_accounting_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="تاریخ پیشنهادی حسابداری",
    )
    mapping_reference = forms.CharField(
        required=False, max_length=255, label="مرجع نگاشت صریح"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), label="دلیل / شرح"
    )

    def __init__(self, *args, organization, allowed_families=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["run"].queryset = PayrollRun.objects.filter(
            organization=organization, status="finalized"
        ).select_related("period")
        if allowed_families is not None:
            allowed = set(allowed_families)
            self.fields["family"].choices = [
                choice
                for choice in FinancialHandoffFamily.choices
                if choice[0] in allowed
            ]


class FinancialHandoffReviewForm(OrganizationForm):
    disposition = forms.ChoiceField(
        choices=(("accepted", "پذیرفته"), ("rejected", "ردشده")), label="نتیجه"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), label="دلیل بررسی"
    )


class EmploymentConfigurationForm(OrganizationForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none(), label="کارمند")
    pay_model = forms.ChoiceField(choices=PayModel.choices, label="مدل پرداخت")
    base_rate = forms.DecimalField(
        max_digits=24, decimal_places=8, min_value=0, label="نرخ مبنا"
    )
    rate_unit = forms.CharField(max_length=40, label="واحد نرخ")
    effective_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="شروع اثر"
    )
    effective_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="پایان اثر",
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(), required=False, label="پروژه"
    )
    site = forms.ModelChoiceField(
        queryset=ProjectSite.objects.none(), required=False, label="کارگاه"
    )
    source_reference = forms.CharField(max_length=255, label="مرجع منبع")
    evidence_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "dir": "ltr"}),
        label="شواهد JSON",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(
            organization=organization, archived_at__isnull=True
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization
        )

    def clean_evidence_json(self) -> dict:
        raw = self.cleaned_data["evidence_json"].strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON معتبر نیست.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("شواهد باید یک شیء JSON باشد.")
        return value


class ComponentForm(OrganizationForm):
    code = forms.CharField(max_length=50, label="کد")
    name = forms.CharField(max_length=255, label="نام")
    kind = forms.ChoiceField(choices=ComponentKind.choices, label="نوع")
    net_effect = forms.ChoiceField(choices=NetEffect.choices, label="اثر بر خالص")
    description = forms.CharField(required=False, widget=forms.Textarea, label="توضیح")
    is_statutory_reserved = forms.BooleanField(
        required=False, label="رزرو برای مرجع قانونی آینده (غیرفعال در این tranche)"
    )


class RuleForm(OrganizationForm):
    component = forms.ModelChoiceField(
        queryset=PayrollComponent.objects.none(), label="جزء حقوق"
    )
    code = forms.CharField(max_length=50, label="کد قاعده")
    name = forms.CharField(max_length=255, label="نام قاعده")
    sequence = forms.IntegerField(min_value=1, initial=100, label="ترتیب")
    method = forms.ChoiceField(choices=CalculationMethod.choices, label="روش")
    fixed_amount = forms.DecimalField(
        required=False, max_digits=24, decimal_places=8, min_value=0, label="مبلغ ثابت"
    )
    rate_source = forms.ChoiceField(choices=RateSource.choices, label="منبع نرخ")
    rate = forms.DecimalField(
        required=False, max_digits=24, decimal_places=8, min_value=0, label="نرخ قاعده"
    )
    percentage = forms.DecimalField(
        required=False, max_digits=12, decimal_places=8, min_value=0, label="درصد"
    )
    basis_component = forms.ModelChoiceField(
        queryset=PayrollComponent.objects.none(), required=False, label="جزء مبنا"
    )
    applicable_pay_models = forms.MultipleChoiceField(
        choices=PayModel.choices, required=False, label="مدل‌های پرداخت مشمول"
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(), required=False, label="پروژه"
    )
    site = forms.ModelChoiceField(
        queryset=ProjectSite.objects.none(), required=False, label="کارگاه"
    )
    effective_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="شروع اثر"
    )
    effective_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="پایان اثر",
    )
    source_reference = forms.CharField(max_length=255, label="مرجع منبع")
    evidence_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "dir": "ltr"}),
        label="شواهد JSON",
    )
    requires_statutory_authority = forms.BooleanField(
        required=False, label="نیازمند مرجع قانونی (فعال‌سازی در این tranche مسدود است)"
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        components = PayrollComponent.objects.filter(
            organization=organization, is_active=True
        )
        self.fields["component"].queryset = components
        self.fields["basis_component"].queryset = components
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization
        )

    def clean_evidence_json(self) -> dict:
        raw = self.cleaned_data["evidence_json"].strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON معتبر نیست.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("شواهد باید یک شیء JSON باشد.")
        return value


class PeriodForm(OrganizationForm):
    code = forms.CharField(max_length=50, label="کد دوره")
    name = forms.CharField(max_length=255, label="نام دوره")
    starts_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="شروع"
    )
    ends_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="پایان"
    )
    cutoff_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label="زمان قطع ورودی",
    )


class RunForm(OrganizationForm):
    period = forms.ModelChoiceField(queryset=PayrollPeriod.objects.none(), label="دوره")
    code = forms.CharField(max_length=60, label="کد اجرا")
    kind = forms.ChoiceField(
        choices=[
            choice
            for choice in PayrollRunKind.choices
            if choice[0] != PayrollRunKind.REVERSAL
        ],
        label="نوع اجرا",
    )
    idempotency_key = forms.CharField(max_length=100, label="کلید تکرارناپذیری")
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.SelectMultiple(attrs={"size": 10}),
        label="کارکنان",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["period"].queryset = PayrollPeriod.objects.filter(
            organization=organization
        )
        self.fields["employees"].queryset = Employee.objects.filter(
            organization=organization, archived_at__isnull=True
        )


class InputForm(OrganizationForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none(), label="کارمند")
    rule = forms.ModelChoiceField(queryset=PayrollRule.objects.none(), label="قاعده")
    quantity = forms.DecimalField(
        max_digits=24, decimal_places=8, min_value=0, label="مقدار"
    )
    source_type = forms.ChoiceField(
        choices=PayrollInputSource.choices, label="نوع منبع"
    )
    source_reference = forms.CharField(max_length=255, label="مرجع منبع")
    source_version = forms.CharField(max_length=100, label="نسخه منبع")
    source_status = forms.ChoiceField(
        choices=(("approved", "تأییدشده"), ("final", "قطعی")), label="وضعیت منبع"
    )
    source_payload_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "dir": "ltr"}),
        label="snapshot منبع JSON",
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(), required=False, label="پروژه"
    )
    site = forms.ModelChoiceField(
        queryset=ProjectSite.objects.none(), required=False, label="کارگاه"
    )

    def __init__(self, *args, organization, run: PayrollRun, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        employee_ids = run.employee_results.values_list("employee_id", flat=True)
        self.fields["employee"].queryset = Employee.objects.filter(pk__in=employee_ids)
        self.fields["rule"].queryset = PayrollRule.objects.filter(
            organization=organization,
            status="active",
            method=CalculationMethod.QUANTITY_TIMES_RATE,
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization
        )

    def clean_source_payload_json(self) -> dict:
        try:
            value = json.loads(self.cleaned_data["source_payload_json"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON معتبر نیست.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("snapshot باید یک شیء JSON باشد.")
        return value


class AdjustmentForm(OrganizationForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none(), label="کارمند")
    component = forms.ModelChoiceField(
        queryset=PayrollComponent.objects.none(), label="جزء حقوق"
    )
    kind = forms.ChoiceField(choices=AdjustmentKind.choices, label="نوع تعدیل")
    amount = forms.DecimalField(
        max_digits=24, decimal_places=8, label="مبلغ (علامت‌دار)"
    )
    effective_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="تاریخ اثر"
    )
    source_reference = forms.CharField(max_length=255, label="مرجع منبع")
    reason = forms.CharField(widget=forms.Textarea, label="دلیل")

    def __init__(self, *args, organization, run: PayrollRun, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        employee_ids = run.employee_results.values_list("employee_id", flat=True)
        self.fields["employee"].queryset = Employee.objects.filter(pk__in=employee_ids)
        self.fields["component"].queryset = PayrollComponent.objects.filter(
            organization=organization, is_active=True, is_statutory_reserved=False
        )


class ReversalForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label="دلیل برگشت")
    idempotency_key = forms.CharField(max_length=100, label="کلید تکرارناپذیری")
    create_replacement = forms.BooleanField(
        required=False, initial=True, label="ایجاد اجرای جایگزین"
    )
    replacement_code = forms.CharField(
        required=False, max_length=60, label="کد اجرای جایگزین"
    )


class StatutoryCalculationForm(OrganizationForm):
    run = forms.ModelChoiceField(queryset=PayrollRun.objects.none(), label="اجرای قطعی")
    kind = forms.ChoiceField(choices=StatutoryCalculationKind.choices, label="نوع")
    record_kind = forms.ChoiceField(
        choices=StatutoryRecordKind.choices, label="نوع سابقه"
    )
    corrects = forms.ModelChoiceField(
        queryset=StatutoryCalculation.objects.none(),
        required=False,
        label="سابقه قبلی",
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="دلیل")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["run"].queryset = PayrollRun.objects.filter(
            organization=organization, status="finalized"
        )
        self.fields["corrects"].queryset = StatutoryCalculation.objects.filter(
            organization=organization
        )


class StatutoryReviewForm(forms.Form):
    disposition = forms.ChoiceField(
        choices=StatutoryReviewDisposition.choices, label="نتیجه"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), label="دلیل بررسی"
    )


class StatutoryIdentityForm(OrganizationForm):
    kind = forms.ChoiceField(choices=StatutoryCalculationKind.choices, label="نوع")
    schema_version = forms.ModelChoiceField(
        queryset=PlatformPolicyVersion.objects.none(), label="نسخه طرح رسمی"
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        label="کارمند (برای هویت کارفرما/کارگاه خالی)",
    )
    identifiers_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "dir": "ltr"}),
        label="شناسه‌های مجاز JSON",
    )
    effective_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="شروع اثر"
    )
    effective_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="پایان اثر",
    )
    source_reference = forms.CharField(max_length=500, label="مرجع منبع")
    supersedes = forms.ModelChoiceField(
        queryset=StatutoryIdentityEvidence.objects.none(),
        required=False,
        label="نسخه قبلی",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["schema_version"].queryset = PlatformPolicyVersion.objects.filter(
            policy__code__in=(
                PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
                EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
            ),
            status="published",
        )
        self.fields["employee"].queryset = Employee.objects.filter(
            organization=organization
        )
        self.fields["supersedes"].queryset = StatutoryIdentityEvidence.objects.filter(
            organization=organization
        )

    def clean_identifiers_json(self) -> dict[str, str]:
        try:
            value = json.loads(self.cleaned_data["identifiers_json"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON شناسه‌ها معتبر نیست.") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("شناسه‌ها باید یک شیء JSON باشند.")
        return value


class StatutoryOutputForm(OrganizationForm):
    output_identifier = forms.CharField(max_length=150, label="شناسه داخلی خروجی")
    corrects = forms.ModelChoiceField(
        queryset=StatutoryOutput.objects.none(),
        required=False,
        label="خروجی قبلی",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["corrects"].queryset = StatutoryOutput.objects.filter(
            organization=organization
        )


class StatutoryExportForm(forms.Form):
    idempotency_key = forms.CharField(max_length=255, label="کلید idempotency")
    correlation_id = forms.CharField(max_length=255, label="شناسه همبستگی")
    status = forms.ChoiceField(
        choices=StatutoryExportStatus.choices, label="وضعیت دستی"
    )
    artifact_name = forms.CharField(max_length=255, label="نام artifact")
    provider_reference = forms.CharField(
        max_length=255, required=False, label="مرجع بیرونی"
    )
    error_code = forms.CharField(max_length=120, required=False, label="کد خطا")
    error_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="شرح رد/خطا",
    )


class StatutoryResolutionForm(forms.Form):
    action = forms.ChoiceField(choices=StatutoryResolutionAction.choices, label="اقدام")
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), label="شرح حل انسانی"
    )
