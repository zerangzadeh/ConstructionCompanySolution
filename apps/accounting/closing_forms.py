from django import forms

from apps.organizations.models import OrganizationMembership

from .forms import AccountingFormMixin, ReasonForm
from .models import Account, AccountType, FiscalYear


class YearEndPairForm(AccountingFormMixin, forms.Form):
    source_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(), label="سال مالی مبدأ"
    )
    target_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(), label="سال مالی بعد"
    )
    reason = forms.CharField(label="دلیل و یادداشت بررسی", widget=forms.Textarea)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("source_year", "target_year"):
            self.fields[name].queryset = FiscalYear.objects.filter(
                organization=organization
            )
        self._style_fields()


class YearEndConfigurationForm(AccountingFormMixin, forms.Form):
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(), label="سال مالی"
    )
    result_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="حساب نتیجه سال",
        help_text="حساب برگ حقوق مالکانه با مانده صفر پیش از بستن",
    )
    retained_account = forms.ModelChoiceField(
        queryset=Account.objects.none(), label="حساب سود و زیان انباشته"
    )
    reason = forms.CharField(label="دلیل تنظیم حساب‌ها", widget=forms.Textarea)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
            organization=organization, status="active"
        )
        accounts = Account.objects.filter(
            organization=organization,
            account_type=AccountType.EQUITY,
            is_posting=True,
            archived_at__isnull=True,
        )
        for name in ("result_account", "retained_account"):
            self.fields[name].queryset = accounts
        self._style_fields()


class YearEndReopenForm(ReasonForm):
    requested_by = forms.ModelChoiceField(
        queryset=OrganizationMembership.objects.none(),
        label="درخواست‌کننده مستقل بازگشایی",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_by"].queryset = OrganizationMembership.objects.filter(
            organization=organization, status="active", user__is_active=True
        )
        self._style_fields()
