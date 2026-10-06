from django import forms

from apps.accounting.models import FiscalPeriod, FiscalPeriodStatus
from apps.fixed_assets.models import (
    AssetBookPolicyVersion,
    AssetSourceReference,
    AssetTransaction,
    AssetTransactionType,
    DepreciationConvention,
    DepreciationLine,
    FixedAsset,
    FixedAssetClassVersion,
    PolicyStatus,
    TransactionStatus,
)
from apps.projects.models import CostCenter, Project, ProjectSite


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "erp-input")


class AssetClassForm(StyledForm):
    code = forms.CharField(label="کد طبقه", max_length=50)
    name = forms.CharField(label="نام طبقه", max_length=160)
    version = forms.IntegerField(label="نسخه", min_value=1)
    effective_from = forms.DateField(
        label="شروع اعتبار", widget=forms.DateInput(attrs={"type": "date"})
    )
    account_mapping_reference = forms.CharField(label="مرجع نگاشت حساب")
    capitalization_policy_reference = forms.CharField(label="مرجع سیاست سرمایه‌ای")


class BookPolicyForm(StyledForm):
    code = forms.CharField(label="کد کتاب", max_length=50)
    version = forms.IntegerField(label="نسخه", min_value=1)
    effective_from = forms.DateField(
        label="شروع اعتبار", widget=forms.DateInput(attrs={"type": "date"})
    )
    monetary_policy_code = forms.CharField(label="کد سیاست پولی")
    monetary_policy_version = forms.CharField(label="نسخه سیاست پولی")
    convention = forms.ChoiceField(
        label="قاعده شروع", choices=DepreciationConvention.choices
    )
    decimal_places = forms.IntegerField(label="دقت", min_value=0, max_value=6)


class AssetForm(StyledForm):
    asset_number = forms.CharField(label="شماره دارایی", max_length=50)
    name = forms.CharField(label="نام دارایی", max_length=255)
    asset_class = forms.ModelChoiceField(
        label="طبقه منتشرشده", queryset=FixedAssetClassVersion.objects.none()
    )
    book_policy = forms.ModelChoiceField(
        label="کتاب منتشرشده", queryset=AssetBookPolicyVersion.objects.none()
    )
    ready_for_use_date = forms.DateField(
        label="تاریخ آماده‌به‌کار", widget=forms.DateInput(attrs={"type": "date"})
    )
    useful_life_months = forms.IntegerField(label="عمر مفید (ماه)", min_value=1)
    residual_value = forms.DecimalField(
        label="ارزش اسقاط", min_value=0, decimal_places=6
    )
    capitalization_basis = forms.DecimalField(
        label="مبنای سرمایه‌ای", min_value=0.000001, decimal_places=6
    )
    evidence_reference = forms.CharField(label="مرجع مدرک")
    project = forms.ModelChoiceField(
        label="پروژه", queryset=Project.objects.none(), required=False
    )
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    cost_center = forms.ModelChoiceField(
        label="مرکز هزینه", queryset=CostCenter.objects.none(), required=False
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_class"].queryset = FixedAssetClassVersion.objects.filter(
            organization=organization, status=PolicyStatus.PUBLISHED
        )
        self.fields["book_policy"].queryset = AssetBookPolicyVersion.objects.filter(
            organization=organization, status=PolicyStatus.PUBLISHED
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization
        )
        self.fields["cost_center"].queryset = CostCenter.objects.filter(
            organization=organization
        )


class SourceForm(StyledForm):
    source_family = forms.ChoiceField(
        label="نوع منبع",
        choices=[
            ("acquisition", "تحصیل"),
            ("construction_ready", "ساخت آماده‌به‌کار"),
            ("legacy_opening", "افتتاحیه کنترل‌شده"),
        ],
    )
    source_public_id = forms.CharField(label="شناسه عمومی منبع")
    source_version = forms.CharField(label="نسخه منبع")
    source_line = forms.CharField(label="خط منبع", required=False)
    source_date = forms.DateField(
        label="تاریخ منبع", widget=forms.DateInput(attrs={"type": "date"})
    )
    amount = forms.DecimalField(label="مبلغ IRR", min_value=0.000001, decimal_places=6)
    evidence_reference = forms.CharField(label="مرجع مدرک")


class CapitalizeForm(StyledForm):
    source = forms.ModelChoiceField(
        label="منبع بررسی‌شده", queryset=AssetSourceReference.objects.none()
    )
    occurrence_key = forms.CharField(label="کلید رخداد", max_length=140)

    def __init__(self, *args, asset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = AssetSourceReference.objects.filter(
            asset=asset, reviewed=True
        )


class DepreciationPreviewForm(StyledForm):
    book_policy = forms.ModelChoiceField(
        label="کتاب", queryset=AssetBookPolicyVersion.objects.none()
    )
    fiscal_period = forms.ModelChoiceField(
        label="دوره باز", queryset=FiscalPeriod.objects.none()
    )
    occurrence_key = forms.CharField(label="کلید اجرا", max_length=140)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book_policy"].queryset = AssetBookPolicyVersion.objects.filter(
            organization=organization, status=PolicyStatus.PUBLISHED
        )
        self.fields["fiscal_period"].queryset = FiscalPeriod.objects.filter(
            organization=organization, status=FiscalPeriodStatus.OPEN
        )


class AssetTransactionForm(StyledForm):
    asset = forms.ModelChoiceField(
        label="دارایی فعال", queryset=FixedAsset.objects.none()
    )
    transaction_type = forms.ChoiceField(
        label="نوع رویداد",
        choices=[
            (AssetTransactionType.ADDITION, "افزایش"),
            (AssetTransactionType.IMPAIRMENT, "کاهش ارزش"),
            (AssetTransactionType.TRANSFER, "انتقال"),
            (AssetTransactionType.DISPOSAL, "واگذاری"),
            (AssetTransactionType.RETIREMENT, "خروج"),
        ],
    )
    occurred_on = forms.DateField(
        label="تاریخ رویداد", widget=forms.DateInput(attrs={"type": "date"})
    )
    amount = forms.DecimalField(label="مبلغ IRR", min_value=0, decimal_places=6)
    occurrence_key = forms.CharField(label="کلید رخداد", max_length=140)
    reason = forms.CharField(label="علت و مدرک", widget=forms.Textarea)
    source = forms.ModelChoiceField(
        label="منبع بررسی‌شده (اختیاری)",
        queryset=AssetSourceReference.objects.none(),
        required=False,
    )
    target_project = forms.ModelChoiceField(
        label="پروژه مقصد انتقال", queryset=Project.objects.none(), required=False
    )
    target_site = forms.ModelChoiceField(
        label="کارگاه مقصد انتقال", queryset=ProjectSite.objects.none(), required=False
    )
    target_cost_center = forms.ModelChoiceField(
        label="مرکز هزینه مقصد انتقال",
        queryset=CostCenter.objects.none(),
        required=False,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = FixedAsset.objects.filter(
            organization=organization, status="active"
        )
        self.fields["source"].queryset = AssetSourceReference.objects.filter(
            organization=organization, reviewed=True
        )
        self.fields["target_project"].queryset = Project.objects.filter(
            organization=organization
        )
        self.fields["target_site"].queryset = ProjectSite.objects.filter(
            organization=organization
        )
        self.fields["target_cost_center"].queryset = CostCenter.objects.filter(
            organization=organization
        )


class ReversalForm(StyledForm):
    occurrence_key = forms.CharField(label="کلید برگشت", max_length=140)
    reason = forms.CharField(label="علت برگشت", widget=forms.Textarea)


class HandoffForm(StyledForm):
    consumer = forms.ChoiceField(
        label="مصرف‌کننده",
        choices=[("accounting", "حسابداری"), ("project_cost", "کنترل پروژه")],
    )
    occurrence_key = forms.CharField(label="کلید پیشنهاد", max_length=140)
    asset_transaction = forms.ModelChoiceField(
        label="رویداد دارایی (یکی را انتخاب کنید)",
        queryset=AssetTransaction.objects.none(),
        required=False,
    )
    depreciation_line = forms.ModelChoiceField(
        label="خط استهلاک (یکی را انتخاب کنید)",
        queryset=DepreciationLine.objects.none(),
        required=False,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_transaction"].queryset = AssetTransaction.objects.filter(
            organization=organization, status=TransactionStatus.FINALIZED
        )
        self.fields["depreciation_line"].queryset = DepreciationLine.objects.filter(
            organization=organization, run__status="finalized"
        ).select_related("asset", "run__fiscal_period")

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("asset_transaction")) == bool(
            cleaned.get("depreciation_line")
        ):
            raise forms.ValidationError("دقیقاً یک منبع پیشنهاد را انتخاب کنید.")
        return cleaned


class ReconciliationForm(StyledForm):
    consumer_reference = forms.CharField(label="مرجع مصرف‌کننده", max_length=120)
    consumer_amount = forms.DecimalField(
        label="مبلغ مصرف‌کننده (اختیاری)", required=False, decimal_places=6
    )
    disposition = forms.CharField(
        label="نتیجه تطبیق", required=False, widget=forms.Textarea
    )
