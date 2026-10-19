from decimal import Decimal
from uuid import uuid4

from django import forms

from apps.accounting.models import FiscalPeriod
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    OrganizationMembership,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project
from apps.treasury.models import PaymentRequest, TreasuryAccount, TreasuryAccountStatus
from core.forms import JalaliDateMixin


class MovementForm(JalaliDateMixin, forms.Form):
    kind = forms.ChoiceField(
        label="نوع حرکت", choices=(("receipt", "دریافت"), ("disbursement", "پرداخت"))
    )
    movement_date = forms.DateField(label="تاریخ حرکت")
    amount = forms.DecimalField(
        label="مبلغ (ریال)",
        max_digits=24,
        decimal_places=6,
        min_value=Decimal("0.000001"),
    )
    account = forms.ModelChoiceField(
        label="حساب خزانه", queryset=TreasuryAccount.objects.none()
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    party = forms.ModelChoiceField(
        label="طرف حساب", queryset=BusinessParty.objects.none(), required=False
    )
    description = forms.CharField(label="شرح", max_length=500)
    origin_request = forms.ModelChoiceField(
        label="درخواست پرداخت مصوب",
        queryset=PaymentRequest.objects.none(),
        required=False,
    )
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput, initial=uuid4, max_length=120
    )

    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=actor, organization=organization)
        self.fields["account"].queryset = TreasuryAccount.objects.filter(
            organization=organization, status=TreasuryAccountStatus.ACTIVE
        )
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        )
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization
        )
        self.fields["origin_request"].queryset = scope_queryset(
            PaymentRequest.objects.filter(
                organization=organization,
                status="approved",
                kind="employee_reimbursement",
            ),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )
        if not has_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.TREASURY_VIEW,
        ):
            self.fields["origin_request"].queryset = PaymentRequest.objects.none()
        self.fields["origin_request"].label_from_instance = lambda item: (
            f"{item.purpose[:60]} · {item.amount} ریال"
        )


class MovementPostForm(forms.Form):
    accounting_preparer = forms.ModelChoiceField(
        label="تهیه‌کننده مستقل حسابداری", queryset=OrganizationMembership.objects.none()
    )
    period = forms.ModelChoiceField(
        label="دوره مالی", queryset=FiscalPeriod.objects.none()
    )
    reason = forms.CharField(label="دلیل", max_length=1000)

    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accounting_preparer"].queryset = (
            OrganizationMembership.objects.filter(
                organization=organization,
                status=MembershipStatus.ACTIVE,
            )
            .exclude(user=actor)
            .select_related("user")
        )
        self.fields["period"].queryset = FiscalPeriod.objects.filter(
            organization=organization
        )


class MovementReverseForm(JalaliDateMixin, MovementPostForm):
    accounting_date = forms.DateField(label="تاریخ برگشت")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accounting_preparer"].label = "درخواست‌کننده مستقل برگشت"
