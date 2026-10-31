from django import forms

from apps.contracts.models import (
    Contract,
    ContractStatus,
    ContractualRecord,
    ContractualRecordKind,
    ContractualRevisionAction,
)
from apps.organizations.authorization import scope_queryset
from apps.organizations.models import InsuranceClassification, OrganizationMembership
from apps.organizations.policy_services import available_insurance_classifications
from apps.parties.models import BusinessParty
from apps.projects.models import Project
from core.business_choices import configure_business_choice, inherit_business_parent
from core.forms import JalaliDateMixin
from core.identifiers import canonicalize_upper_identifier


class ContractForm(JalaliDateMixin, forms.ModelForm):
    """Form for creating a contract in the active organization."""

    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        empty_label="پروژه را انتخاب کنید",
    )

    class Meta:
        model = Contract
        fields = [  # noqa: RUF012
            "project",
            "contract_number",
            "title",
            "counterparty_name",
            "party",
            "direction",
            "contract_type",
            "status",
            "contract_value",
            "signed_at",
            "start_date",
            "end_date",
            "notes",
        ]

    def __init__(
        self,
        *args,
        organization=None,
        membership: OrganizationMembership | None = None,
        context_project=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if (
            isinstance(membership, OrganizationMembership)
            and organization is not None
            and membership.organization_id == organization.pk
        ):
            self.fields["project"].queryset = scope_queryset(
                Project.objects.filter(
                    organization=organization, deleted_at__isnull=True
                ),
                membership=membership,
                project_lookup="pk",
            ).order_by("name")
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")
        self.fields.pop("counterparty_name")
        self.fields["party"].required = True
        self.fields["party"].label = "طرف قرارداد"
        self.fields["direction"].label = "جهت قرارداد"
        for name in ("project", "party"):
            if name == "project" and context_project is not None:
                continue
            configure_business_choice(self, name, "contract")
        if context_project is not None:
            inherit_business_parent(
                self, "project", context_project, detail_route="projects:detail"
            )

    def clean_party(self):
        party = self.cleaned_data["party"]
        self.instance.counterparty_name = party.display_name
        return party

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ContractStatus.values:
            raise forms.ValidationError("وضعیت قرارداد معتبر نیست.")
        return status

    def clean_contract_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["contract_number"])

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "تاریخ پایان قرارداد نمی‌تواند پیش از تاریخ شروع باشد."
            )
        return cleaned_data


class ContractualRecordForm(JalaliDateMixin, forms.ModelForm):
    class Meta:
        model = ContractualRecord
        fields = [  # noqa: RUF012
            "contract",
            "kind",
            "record_number",
            "title",
            "description",
            "notice_reference",
            "notice_date",
            "requested_amount",
            "requested_eot_days",
            "valuation_assumptions",
            "cost_impact_assumptions",
            "schedule_impact_assumptions",
            "contract_value_impact_assumptions",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = Contract.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            status=ContractStatus.ACTIVE,
            party__isnull=False,
        ).select_related("project", "party")

    def clean_kind(self) -> str:
        kind = self.cleaned_data["kind"]
        if kind not in ContractualRecordKind.values:
            raise forms.ValidationError("نوع رکورد قراردادی معتبر نیست.")
        return kind


class ContractualDecisionForm(forms.Form):
    outcome = forms.ChoiceField(
        label="تصمیم",
        choices=(("approved", "تأیید"), ("returned", "بازگردانی")),
    )
    reason = forms.CharField(label="دلیل تصمیم", widget=forms.Textarea)
    entitlement_approved = forms.TypedChoiceField(
        label="تصمیم صریح استحقاق",
        choices=(("true", "استحقاق تأیید شد"), ("false", "استحقاق تأیید نشد")),
        coerce=lambda value: value == "true",
        required=False,
    )
    approved_amount = forms.DecimalField(
        label="مبلغ صریحاً تأییدشده", max_digits=18, decimal_places=4, required=False
    )
    approved_eot_days = forms.IntegerField(
        label="روزهای صریحاً تأییدشده تمدید مدت", min_value=0, required=False
    )
    delay_responsibility = forms.CharField(
        label="مسئولیت تأخیر صریحاً تأییدشده", widget=forms.Textarea, required=False
    )

    def clean(self):
        values = super().clean()
        if values.get("outcome") == "approved" and "entitlement_approved" not in values:
            raise forms.ValidationError("برای تأیید، تصمیم صریح استحقاق الزامی است.")
        return values


class ContractualRevisionForm(forms.Form):
    revision_action = forms.ChoiceField(
        label="نوع بازنگری",
        choices=(
            (ContractualRevisionAction.CORRECTION, "اصلاح / جایگزینی"),
            (ContractualRevisionAction.CANCELLATION, "ابطال پیوندخورده"),
        ),
    )
    reason = forms.CharField(label="دلیل", widget=forms.Textarea)
    title = forms.CharField(label="عنوان نسخه جدید", required=False)
    description = forms.CharField(
        label="شرح نسخه جدید", widget=forms.Textarea, required=False
    )


class ContractualWithdrawalForm(forms.Form):
    reason = forms.CharField(label="دلیل استرداد", widget=forms.Textarea)


class ContractInsuranceClassificationForm(forms.Form):
    insurance_classification = forms.ModelChoiceField(
        label="طبقه‌بندی بیمه", queryset=InsuranceClassification.objects.none()
    )
    reason = forms.CharField(
        label="دلیل انتخاب", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, on_date, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "insurance_classification"
        ].queryset = available_insurance_classifications(on_date=on_date)
