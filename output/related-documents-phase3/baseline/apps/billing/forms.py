from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.contracts.models import (
    Contract,
    ContractDirection,
    ContractItem,
    ContractStatus,
    ContractType,
)
from apps.documents.models import DocumentVersion
from apps.documents.services import (
    get_organization_document,
    get_organization_documents,
)
from apps.organizations.authorization import scope_queryset
from apps.organizations.models import Organization, OrganizationMembership
from apps.treasury.models import (
    TreasuryMovement,
    TreasuryMovementKind,
    TreasuryMovementStatus,
)
from core.forms import JalaliDateMixin, attach_parent_choice_ui

from .commercial_services import get_compliance_evidence
from .models import (
    AssuranceRevisionAction,
    ComplianceEvidenceKind,
    ContractComplianceEvidence,
    EvidenceExpiryKind,
    GuaranteeExposureSide,
    GuaranteeType,
    PayableCertificate,
    ProgressClaim,
    RetentionReleaseCorrectionKind,
    StatutoryRecordKind,
    SubmissionResolutionAction,
    TaxpayerInvoice,
)


class _CommercialEvidenceForm(JalaliDateMixin, forms.Form):
    def _configure_create(
        self,
        *,
        organization: Organization,
        membership: OrganizationMembership | None,
        actor: User | None,
    ) -> None:
        """Restrict create choices through existing Contract and DMS authority."""
        for name in ("contract", "document_version", "evidence_document_version"):
            if name in self.fields:
                self.fields[name].queryset = self.fields[name].queryset.none()
        if (
            not isinstance(membership, OrganizationMembership)
            or membership.organization_id != organization.pk
            or actor is None
            or membership.user_id != actor.pk
        ):
            return
        self._configure(organization)
        self.fields["contract"].queryset = scope_queryset(
            self.fields["contract"].queryset,
            membership=membership,
            project_lookup="project_id",
        )
        visible_document_ids = []
        try:
            candidates = get_organization_documents(
                user=actor, organization=organization
            )
            for document_id in candidates.values_list("pk", flat=True):
                try:
                    get_organization_document(
                        user=actor,
                        organization=organization,
                        document_id=str(document_id),
                    )
                except PermissionDenied:
                    continue
                visible_document_ids.append(document_id)
        except PermissionDenied:
            pass
        for name in ("document_version", "evidence_document_version"):
            if name in self.fields:
                self.fields[name].queryset = self.fields[name].queryset.filter(
                    document_id__in=visible_document_ids
                )

    def _configure(self, organization) -> None:
        if "contract" in self.fields:
            self.fields["contract"].queryset = Contract.objects.filter(
                organization=organization,
                status=ContractStatus.ACTIVE,
                deleted_at__isnull=True,
                party__isnull=False,
            ).select_related("project", "party")
        for name in ("document_version", "evidence_document_version"):
            if name in self.fields:
                self.fields[name].queryset = DocumentVersion.objects.filter(
                    organization=organization,
                    document__archived_at__isnull=True,
                ).select_related("document")


class GuaranteeForm(_CommercialEvidenceForm):
    contract = forms.ModelChoiceField(label="قرارداد", queryset=Contract.objects.none())
    guarantee_type = forms.ChoiceField(
        label="نوع ضمانت‌نامه", choices=GuaranteeType.choices
    )
    exposure_side = forms.ChoiceField(
        label="سمت مواجهه", choices=GuaranteeExposureSide.choices
    )
    instrument_reference = forms.CharField(label="شماره/مرجع ابزار", max_length=120)
    issuer_name = forms.CharField(label="صادرکننده", max_length=255)
    amount = forms.DecimalField(label="مبلغ اسمی", max_digits=18, decimal_places=4)
    issued_on = forms.DateField(
        label="تاریخ صدور", widget=forms.DateInput(attrs={"type": "date"})
    )
    effective_from = forms.DateField(
        label="تاریخ اثر", widget=forms.DateInput(attrs={"type": "date"})
    )
    expiry_kind = forms.ChoiceField(
        label="نوع انقضا", choices=EvidenceExpiryKind.choices
    )
    expires_on = forms.DateField(
        label="تاریخ انقضا",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    evidence_document_version = forms.ModelChoiceField(
        label="نسخه سند شاهد", queryset=DocumentVersion.objects.none()
    )
    reason = forms.CharField(label="دلیل ثبت", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, membership=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_create(
            organization=organization, membership=membership, actor=actor
        )


class GuaranteeRevisionForm(_CommercialEvidenceForm):
    revision_action = forms.ChoiceField(
        label="نوع اقدام",
        choices=[
            (AssuranceRevisionAction.CORRECTION, "اصلاح"),
            (AssuranceRevisionAction.RENEWAL, "تمدید"),
            (AssuranceRevisionAction.RELEASE, "آزادسازی"),
        ],
    )
    amount = forms.DecimalField(
        label="مبلغ اسمی جدید", max_digits=18, decimal_places=4, required=False
    )
    instrument_reference = forms.CharField(
        label="مرجع جدید", max_length=120, required=False
    )
    issuer_name = forms.CharField(
        label="صادرکننده جدید", max_length=255, required=False
    )
    issued_on = forms.DateField(
        label="تاریخ صدور جدید",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    effective_from = forms.DateField(
        label="تاریخ اثر جدید",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    expiry_kind = forms.ChoiceField(
        label="نوع انقضای جدید", choices=EvidenceExpiryKind.choices, required=False
    )
    expires_on = forms.DateField(
        label="تاریخ انقضای جدید",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    evidence_document_version = forms.ModelChoiceField(
        label="نسخه سند شاهد", queryset=DocumentVersion.objects.none()
    )
    reason = forms.CharField(
        label="دلیل اقدام", widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure(organization)


class ComplianceEvidenceForm(_CommercialEvidenceForm):
    contract = forms.ModelChoiceField(label="قرارداد", queryset=Contract.objects.none())
    evidence_kind = forms.ChoiceField(
        label="نوع شاهد", choices=ComplianceEvidenceKind.choices
    )
    reference = forms.CharField(label="شماره/مرجع شاهد", max_length=120)
    issuing_authority = forms.CharField(label="مرجع صادرکننده", max_length=255)
    effective_from = forms.DateField(
        label="تاریخ اثر", widget=forms.DateInput(attrs={"type": "date"})
    )
    expiry_kind = forms.ChoiceField(
        label="نوع انقضا", choices=EvidenceExpiryKind.choices
    )
    expires_on = forms.DateField(
        label="تاریخ انقضا",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    document_version = forms.ModelChoiceField(
        label="نسخه سند شاهد", queryset=DocumentVersion.objects.none()
    )
    reason = forms.CharField(label="دلیل ثبت", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, membership=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "contract" in self.fields:
            self._configure_create(
                organization=organization, membership=membership, actor=actor
            )
        else:
            # Revision forms inherit this initializer behind their existing reader gate.
            self._configure(organization)


class ComplianceEvidenceRevisionForm(ComplianceEvidenceForm):
    contract = None
    evidence_kind = None
    revision_action = forms.ChoiceField(
        label="نوع اقدام",
        choices=[
            (AssuranceRevisionAction.CORRECTION, "اصلاح"),
            (AssuranceRevisionAction.RENEWAL, "تمدید"),
        ],
    )


class RetentionReleaseForm(_CommercialEvidenceForm):
    contract = forms.ModelChoiceField(
        label="پیمان جزء", queryset=Contract.objects.none()
    )
    release_date = forms.DateField(
        label="تاریخ آزادسازی", widget=forms.DateInput(attrs={"type": "date"})
    )
    amount = forms.DecimalField(label="مبلغ آزادسازی", max_digits=18, decimal_places=4)
    evidence_document_version = forms.ModelChoiceField(
        label="نسخه سند مجوز/شاهد", queryset=DocumentVersion.objects.none()
    )
    clearance_evidence = forms.ModelChoiceField(
        label="مفاصاحساب تأییدشده",
        queryset=ContractComplianceEvidence.objects.none(),
        required=False,
    )

    def __init__(self, *args, organization, membership=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_create(
            organization=organization, membership=membership, actor=actor
        )
        self.fields["contract"].queryset = self.fields["contract"].queryset.filter(
            direction=ContractDirection.PAYABLE, contract_type=ContractType.SUBCONTRACT
        )
        self.fields[
            "clearance_evidence"
        ].queryset = ContractComplianceEvidence.objects.none()
        if (
            not isinstance(membership, OrganizationMembership)
            or membership.organization_id != organization.pk
            or actor is None
            or membership.user_id != actor.pk
        ):
            return
        try:
            self.fields["clearance_evidence"].queryset = get_compliance_evidence(
                actor=actor, organization=organization
            ).filter(evidence_kind=ComplianceEvidenceKind.CLEARANCE, status="approved")
        except PermissionDenied:
            pass

        attach_parent_choice_ui(self, "clearance_evidence", "contract", "contract_id")


class RetentionReleaseCorrectionForm(_CommercialEvidenceForm):
    correction_kind = forms.ChoiceField(
        label="نوع اصلاح",
        choices=[
            (RetentionReleaseCorrectionKind.REPLACEMENT, "اصلاح جایگزین"),
            (RetentionReleaseCorrectionKind.CANCELLATION, "ابطال"),
        ],
    )
    amount = forms.DecimalField(
        label="مبلغ جایگزین", max_digits=18, decimal_places=4, required=False
    )
    evidence_document_version = forms.ModelChoiceField(
        label="نسخه سند شاهد", queryset=DocumentVersion.objects.none()
    )
    clearance_evidence = forms.ModelChoiceField(
        label="مفاصاحساب تأییدشده",
        queryset=ContractComplianceEvidence.objects.none(),
        required=False,
    )
    reason = forms.CharField(
        label="دلیل اصلاح", widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure(organization)
        self.fields[
            "clearance_evidence"
        ].queryset = ContractComplianceEvidence.objects.filter(
            organization=organization,
            evidence_kind=ComplianceEvidenceKind.CLEARANCE,
            status="approved",
        )


class TaxpayerInvoiceForm(forms.Form):
    source_claim = forms.ModelChoiceField(
        label="صورت‌وضعیت تأییدشده", queryset=ProgressClaim.objects.none()
    )
    record_kind = forms.ChoiceField(
        label="نوع صورتحساب", choices=StatutoryRecordKind.choices
    )
    corrects = forms.ModelChoiceField(
        label="نسخه پیشین",
        queryset=TaxpayerInvoice.objects.none(),
        required=False,
    )
    reason = forms.CharField(label="دلیل ثبت", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_claim"].queryset = ProgressClaim.objects.filter(
            organization=organization, status="approved"
        ).select_related("contract")
        self.fields["corrects"].queryset = TaxpayerInvoice.objects.filter(
            organization=organization, status="approved"
        ).select_related("contract")


class ContractorComplianceAssessmentForm(forms.Form):
    source_certificate = forms.ModelChoiceField(
        label="گواهی پرداخت تأییدشده", queryset=PayableCertificate.objects.none()
    )
    clearance_evidence = forms.ModelChoiceField(
        label="مفاصاحساب تأییدشده",
        queryset=ContractComplianceEvidence.objects.none(),
        required=False,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_certificate"].queryset = PayableCertificate.objects.filter(
            organization=organization, status="approved"
        ).select_related("contract")
        self.fields[
            "clearance_evidence"
        ].queryset = ContractComplianceEvidence.objects.filter(
            organization=organization,
            evidence_kind=ComplianceEvidenceKind.CLEARANCE,
            status="approved",
        ).select_related("contract")

        attach_parent_choice_ui(
            self,
            "clearance_evidence",
            "source_certificate",
            "contract_id",
            parent_value_attribute="contract_id",
        )


class StatutorySubmissionForm(forms.Form):
    idempotency_key = forms.CharField(
        label="کلید تکرارناپذیری",
        max_length=255,
        widget=forms.HiddenInput,
        initial=uuid4,
    )
    correlation_id = forms.UUIDField(
        label="شناسه همبستگی", widget=forms.HiddenInput, initial=uuid4
    )


class SubmissionResolutionForm(forms.Form):
    action = forms.ChoiceField(
        label="اقدام", choices=SubmissionResolutionAction.choices
    )
    note = forms.CharField(
        label="شرح بررسی انسانی", widget=forms.Textarea(attrs={"rows": 3})
    )
    provider_reference = forms.CharField(
        label="مرجع provider", max_length=255, required=False
    )


class ClaimSettlementAllocationForm(JalaliDateMixin, forms.Form):
    """Choose a posted Treasury receipt; Subledger owns capacity and reversal."""

    movement = forms.ModelChoiceField(
        label="دریافت خزانه‌داری", queryset=TreasuryMovement.objects.none()
    )
    amount = forms.DecimalField(label="مبلغ تسویه", max_digits=18, decimal_places=2)
    effective_date = forms.DateField(
        label="تاریخ مؤثر", widget=forms.DateInput(attrs={"type": "date"})
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=120)
    reason = forms.CharField(
        label="دلیل تسویه", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, organization, claim, **kwargs):
        from uuid import uuid4

        super().__init__(*args, **kwargs)
        self.fields["idempotency_key"].initial = str(uuid4())
        if claim.contract.party_id:
            self.fields["movement"].queryset = TreasuryMovement.objects.filter(
                organization=organization,
                project_id=claim.project_id,
                party_id=claim.contract.party_id,
                kind=TreasuryMovementKind.RECEIPT,
                status=TreasuryMovementStatus.POSTED,
                reverses__isnull=True,
                reversal_movement__isnull=True,
            ).order_by("movement_date", "pk")

    def clean_reason(self) -> str:
        return self.cleaned_data["reason"].strip()


class PayableMeasurementForm(JalaliDateMixin, forms.Form):
    contract_item = forms.ModelChoiceField(
        label="ردیف پیمان جزء", queryset=ContractItem.objects.none()
    )
    measured_on = forms.DateField(
        label="تاریخ اندازه‌گیری", widget=forms.DateInput(attrs={"type": "date"})
    )
    period_quantity = forms.DecimalField(
        label="مقدار دوره", max_digits=18, decimal_places=4
    )
    cumulative_quantity = forms.DecimalField(
        label="مقدار تجمعی", max_digits=18, decimal_places=4
    )
    evidence_reference = forms.CharField(label="مرجع شواهد", max_length=255)

    def __init__(self, *args, organization, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract_item"].queryset = ContractItem.objects.none()
        if (
            not isinstance(membership, OrganizationMembership)
            or membership.organization_id != organization.pk
        ):
            return
        self.fields["contract_item"].queryset = scope_queryset(
            ContractItem.objects.filter(
                organization=organization,
                contract__direction=ContractDirection.PAYABLE,
                contract__contract_type=ContractType.SUBCONTRACT,
                contract__status=ContractStatus.ACTIVE,
                contract__deleted_at__isnull=True,
            )
            .select_related("contract")
            .order_by("contract__contract_number", "sort_order"),
            membership=membership,
            project_lookup="contract__project_id",
        )


class PayableCertificateForm(JalaliDateMixin, forms.Form):
    contract = forms.ModelChoiceField(
        label="پیمان جزء", queryset=Contract.objects.none()
    )
    period_start = forms.DateField(
        label="شروع دوره", widget=forms.DateInput(attrs={"type": "date"})
    )
    period_end = forms.DateField(
        label="پایان دوره", widget=forms.DateInput(attrs={"type": "date"})
    )
    measurement_cutoff = forms.DateField(
        label="تاریخ قطع اندازه‌گیری",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, organization, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = Contract.objects.none()
        if (
            not isinstance(membership, OrganizationMembership)
            or membership.organization_id != organization.pk
        ):
            return
        self.fields["contract"].queryset = scope_queryset(
            Contract.objects.filter(
                organization=organization,
                direction=ContractDirection.PAYABLE,
                contract_type=ContractType.SUBCONTRACT,
                status=ContractStatus.ACTIVE,
                deleted_at__isnull=True,
            ).order_by("contract_number"),
            membership=membership,
            project_lookup="project_id",
        )


class PayableBackChargeForm(forms.Form):
    amount = forms.DecimalField(label="مبلغ کسر", max_digits=18, decimal_places=2)
    description = forms.CharField(label="شرح", max_length=255)
    evidence = forms.CharField(label="مرجع شواهد", max_length=1000)


class PayableCertificateCorrectionForm(forms.Form):
    correction_kind = forms.ChoiceField(
        label="نوع اصلاح",
        choices=(("replacement", "اصلاح جایگزین"), ("cancellation", "ابطال")),
    )
    reason = forms.CharField(
        label="دلیل", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )
