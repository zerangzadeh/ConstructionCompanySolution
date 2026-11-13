from django import forms
from django.core.exceptions import PermissionDenied

from apps.contracts.models import (
    Contract,
    ContractDirection,
    ContractStatus,
    ContractualRecordKind,
    ContractualRevisionAction,
)
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import (
    BusinessPermissionCode,
    InsuranceClassification,
    OrganizationMembership,
)
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
        self.fields["direction"].label = "سمت قرارداد"
        direction_labels = {
            ContractDirection.RECEIVABLE: "با کارفرما",
            ContractDirection.PAYABLE: "با پیمانکار / تأمین‌کننده",
        }
        self.fields["direction"].choices = [
            (value, direction_labels.get(value, label))
            for value, label in self.fields["direction"].choices
        ]
        for name in ("direction", "contract_type"):
            self.fields[name].choices = [
                (value, "انتخاب کنید…" if value == "" else label)
                for value, label in self.fields[name].choices
            ]
        self.fields["contract_number"].widget.attrs.update(
            {"placeholder": "مثال: CNT-1405-001", "dir": "ltr"}
        )
        self.fields["title"].widget.attrs["placeholder"] = (
            "عنوان کوتاه و دقیق قرارداد را وارد کنید…"
        )
        self.fields["notes"].widget.attrs.update(
            {
                "rows": 2,
                "placeholder": "نکات مهم و توضیحات مرتبط با قرارداد را وارد کنید…",
            }
        )
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


class ContractualRecordForm(JalaliDateMixin, forms.Form):
    """Validate browser inputs before the service creates the governed record."""

    contract = forms.ModelChoiceField(label="قرارداد", queryset=Contract.objects.none())
    kind = forms.ChoiceField(label="نوع رکورد", choices=ContractualRecordKind.choices)
    record_number = forms.CharField(label="شماره رکورد", max_length=80)
    title = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", widget=forms.Textarea)
    notice_reference = forms.CharField(
        label="مرجع ابلاغ", max_length=160, required=False
    )
    notice_date = forms.DateField(label="تاریخ ابلاغ", required=False)
    requested_amount = forms.DecimalField(
        label="مبلغ درخواستی",
        max_digits=18,
        decimal_places=4,
        min_value=0,
        required=False,
    )
    requested_eot_days = forms.IntegerField(
        label="روز تمدید درخواستی", min_value=0, required=False
    )
    valuation_assumptions = forms.CharField(
        label="فرض ارزش‌گذاری", widget=forms.Textarea, required=False
    )
    cost_impact_assumptions = forms.CharField(
        label="فرض اثر هزینه", widget=forms.Textarea, required=False
    )
    schedule_impact_assumptions = forms.CharField(
        label="فرض اثر برنامه", widget=forms.Textarea, required=False
    )
    contract_value_impact_assumptions = forms.CharField(
        label="فرض اثر مبلغ قرارداد", widget=forms.Textarea, required=False
    )

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None or organization is None:
            return
        try:
            membership = require_business_permission(
                user=user,
                organization=organization,
                permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
                allow_any_scope=True,
                message="اجازه تهیه رکورد قراردادی را ندارید.",
            )
        except PermissionDenied:
            return
        self.fields["contract"].queryset = scope_queryset(
            Contract.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                project__deleted_at__isnull=True,
                status=ContractStatus.ACTIVE,
                party__isnull=False,
            ).select_related("project", "party"),
            membership=membership,
            project_lookup="project_id",
        )


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
