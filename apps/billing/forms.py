from django import forms

from apps.payments.models import (
    PaymentAllocation,
    PaymentAllocationStatus,
    PaymentDirection,
    PaymentStatus,
)


class ClaimSettlementAllocationForm(forms.Form):
    """Select an already-posted receipt allocation for one approved claim."""

    payment_allocation = forms.ModelChoiceField(
        label="تخصیص دریافت",
        queryset=PaymentAllocation.objects.none(),
    )
    amount = forms.DecimalField(label="مبلغ تسویه", max_digits=18, decimal_places=2)
    reason = forms.CharField(
        label="دلیل تسویه",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, organization, claim, **kwargs):
        super().__init__(*args, **kwargs)
        if not claim.contract.party_id:
            return
        self.fields["payment_allocation"].queryset = (
            PaymentAllocation.objects.filter(
                organization=organization,
                contract=claim.contract,
                status=PaymentAllocationStatus.ACTIVE,
                payment__status=PaymentStatus.POSTED,
                payment__direction=PaymentDirection.RECEIPT,
                payment__project=claim.project,
                payment__party=claim.contract.party,
            )
            .select_related("payment", "contract")
            .order_by("payment__paid_on", "payment__payment_number")
        )

    def clean_reason(self) -> str:
        return self.cleaned_data["reason"].strip()
