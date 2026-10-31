"""Presentation-only forms over the existing receivable services."""

from django import forms

from apps.contracts.models import Contract, ContractDirection, ContractStatus
from apps.contracts.services import get_organization_contracts
from apps.organizations.form_scoping import normalized_uuid
from core.business_choices import configure_business_choice, inherit_business_parent
from core.forms import JalaliDateMixin

from .models import ProjectBaseline, ProjectBaselineStatus
from .services import get_project_baselines


class ClaimCreateForm(JalaliDateMixin, forms.Form):
    contract = forms.ModelChoiceField(label="قرارداد", queryset=Contract.objects.none())
    baseline = forms.ModelChoiceField(
        label="مبنای اندازه‌گیری",
        queryset=ProjectBaseline.objects.none(),
        help_text="مبنای تأییدشده همین قرارداد را انتخاب کنید.",
    )
    period_start = forms.DateField(label="شروع دوره")
    period_end = forms.DateField(label="پایان دوره")
    measurement_cutoff = forms.DateField(label="تاریخ نهایی اندازه‌گیری")

    def __init__(
        self,
        *args,
        organization,
        actor,
        active_project=None,
        context_contract=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages["required"] = "این فیلد را تکمیل کنید."
        contracts = (
            get_organization_contracts(user=actor, organization=organization)
            .filter(
                direction=ContractDirection.RECEIVABLE,
                status=ContractStatus.ACTIVE,
                project__deleted_at__isnull=True,
            )
            .order_by("title", "pk")
        )
        if context_contract is not None:
            contracts = contracts.filter(pk=context_contract.pk)
        self.fields["contract"].queryset = contracts
        value = (
            self.data.get("contract") if self.is_bound else self.initial.get("contract")
        )
        if not value and not self.is_bound and active_project:
            candidates = list(contracts.filter(project=active_project)[:2])
            if len(candidates) == 1:
                value = self.initial["contract"] = candidates[0].pk
        try:
            selected = contracts.filter(pk=value).first() if value else None
        except (ValueError, forms.ValidationError):
            selected = None
        if context_contract is not None:
            selected = context_contract
        self.selected_contract = selected
        baselines = get_project_baselines(
            actor=actor, organization=organization
        ).filter(
            status=ProjectBaselineStatus.APPROVED,
        )
        self.fields["baseline"].queryset = (
            baselines.filter(
                contract=selected, project_id=selected.project_id
            ).order_by("-version", "pk")
            if selected
            else baselines.none()
        )
        if not self.is_bound and selected and "baseline" not in self.initial:
            candidates = list(self.fields["baseline"].queryset[:2])
            if len(candidates) == 1:
                self.initial["baseline"] = candidates[0].pk
        self.no_eligible_baseline = (
            context_contract is not None
            and not self.fields["baseline"].queryset.exists()
        )
        for name in ("contract", "baseline"):
            if name == "contract" and context_contract is not None:
                continue
            configure_business_choice(
                self, name, "claim", parent="contract" if name == "baseline" else None
            )
        if context_contract is not None:
            inherit_business_parent(
                self, "contract", context_contract, detail_route="contracts:detail"
            )

    def clean(self):
        values = super().clean()
        selected = values.get("contract")
        if (
            selected
            and "project" in self.data
            and normalized_uuid(self.data["project"]) != selected.project_id
        ):
            raise forms.ValidationError("پروژه ارسال‌شده با قرارداد هم‌خوان نیست.")
        start, end, cutoff = (
            values.get(n) for n in ("period_start", "period_end", "measurement_cutoff")
        )
        if start and end and end < start:
            self.add_error("period_end", "پایان دوره نمی‌تواند پیش از شروع دوره باشد.")
        if start and end and cutoff and not start <= cutoff <= end:
            self.add_error(
                "measurement_cutoff", "تاریخ اندازه‌گیری باید در بازه دوره باشد."
            )
        return values


class ClaimDecisionForm(forms.Form):
    reason = forms.CharField(
        label="دلیل تصمیم",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"required": "دلیل تصمیم را وارد کنید."},
    )


class ClaimCorrectionForm(ClaimDecisionForm):
    correction_kind = forms.ChoiceField(
        label="نوع اصلاح",
        choices=(
            ("replacement", "جایگزینی با نسخه اصلاحی"),
            ("cancellation", "ابطال با حفظ تاریخچه"),
        ),
    )
