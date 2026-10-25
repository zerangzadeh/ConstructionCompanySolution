from uuid import uuid4

from django import forms
from django.utils import timezone

from apps.materials.models import Material
from apps.organizations.authorization import scope_queryset
from apps.organizations.models import OrganizationMembership
from apps.parties.models import BusinessParty, PartyRoleType
from apps.procurement.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
)
from apps.projects.models import Project
from core.forms import JalaliDateMixin, attach_parent_choice_ui


class _StyledForm(JalaliDateMixin, forms.Form):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", field_class)


class PurchaseRequestForm(_StyledForm):
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    request_number = forms.CharField(label="شماره درخواست", max_length=80)
    title = forms.CharField(label="عنوان درخواست", max_length=255)
    required_by = forms.DateField(
        label="تاریخ موردنیاز",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self,
        *args: object,
        organization,
        membership: OrganizationMembership | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not isinstance(membership, OrganizationMembership) or (
            membership.organization_id != organization.pk
        ):
            return
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        ).order_by("name")


class RequestItemForm(_StyledForm):
    material = forms.ModelChoiceField(label="مصالح", queryset=Material.objects.none())
    quantity = forms.DecimalField(label="مقدار", min_value=0.0001, decimal_places=4)
    description = forms.CharField(label="شرح ردیف", max_length=255, required=False)

    def __init__(self, *args: object, organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = (
            Material.objects.filter(
                organization=organization,
                is_active=True,
                archived_at__isnull=True,
                unit_of_measure__is_active=True,
                unit_of_measure__archived_at__isnull=True,
            )
            .select_related("unit_of_measure")
            .order_by("name")
        )


class PurchaseOrderForm(_StyledForm):
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    purchase_request = forms.ModelChoiceField(
        label="درخواست خرید",
        queryset=PurchaseRequest.objects.none(),
        required=False,
        empty_label="بدون درخواست خرید",
    )
    supplier = forms.ModelChoiceField(
        label="تأمین‌کننده", queryset=BusinessParty.objects.none()
    )
    order_number = forms.CharField(label="شماره سفارش", max_length=80)
    order_date = forms.DateField(
        label="تاریخ سفارش", widget=forms.DateInput(attrs={"type": "date"})
    )
    expected_delivery_date = forms.DateField(
        label="تاریخ تحویل موردانتظار",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self,
        *args: object,
        organization,
        membership: OrganizationMembership | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not isinstance(membership, OrganizationMembership) or (
            membership.organization_id != organization.pk
        ):
            return
        # PO services require project authority; a site grant cannot add its parent.
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        ).order_by("name")
        self.fields["purchase_request"].queryset = (
            scope_queryset(
                PurchaseRequest.objects.filter(
                    organization=organization,
                    status="approved",
                    project__deleted_at__isnull=True,
                ),
                membership=membership,
                project_lookup="project_id",
            )
            .select_related("project")
            .order_by("-created_at")
        )
        self.fields["supplier"].queryset = (
            BusinessParty.objects.filter(
                organization=organization,
                archived_at__isnull=True,
                roles__role=PartyRoleType.SUPPLIER,
            )
            .distinct()
            .order_by("display_name")
        )

        attach_parent_choice_ui(self, "purchase_request", "project", "project_id")

    def clean(self):
        cleaned = super().clean()
        request = cleaned.get("purchase_request")
        project = cleaned.get("project")
        if request and project and request.project_id != project.pk:
            self.add_error(
                "purchase_request", "درخواست خرید باید به همین پروژه تعلق داشته باشد."
            )
        return cleaned


class OrderItemForm(RequestItemForm):
    unit_price = forms.DecimalField(label="قیمت واحد", min_value=0, decimal_places=2)
    purchase_request_item = forms.ModelChoiceField(
        label="ردیف درخواست خرید",
        queryset=PurchaseRequestItem.objects.none(),
        required=False,
        empty_label="بدون ردیف درخواست خرید",
    )

    def __init__(
        self,
        *args: object,
        organization,
        purchase_order: PurchaseOrder,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["purchase_request_item"] = forms.ModelChoiceField(
            label="ردیف درخواست خرید",
            queryset=purchase_order.purchase_request.items.select_related("material")
            if purchase_order.purchase_request_id
            else PurchaseOrderItem.objects.none(),
            required=False,
            empty_label="بدون ردیف درخواست خرید",
        )
        self.fields["purchase_request_item"].widget.attrs["class"] = self.fields[
            "material"
        ].widget.attrs["class"]

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("purchase_request_item")
        material = cleaned.get("material")
        if item and material and item.material_id != material.pk:
            self.add_error("material", "مصالح باید با ردیف درخواست مطابقت داشته باشد.")
        return cleaned


class GoodsReceiptForm(_StyledForm):
    purchase_order = forms.ModelChoiceField(
        label="سفارش خرید", queryset=PurchaseOrder.objects.none()
    )
    receipt_number = forms.CharField(label="شماره رسید کالا", max_length=80)
    received_at = forms.DateTimeField(
        label="زمان دریافت",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self,
        *args: object,
        organization,
        membership: OrganizationMembership | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not isinstance(membership, OrganizationMembership) or (
            membership.organization_id != organization.pk
        ):
            return
        self.fields["purchase_order"].queryset = (
            scope_queryset(
                PurchaseOrder.objects.filter(
                    organization=organization,
                    status="issued",
                    project__deleted_at__isnull=True,
                ),
                membership=membership,
                project_lookup="project_id",
            )
            .select_related("project", "supplier")
            .order_by("-order_date")
        )

    def clean_received_at(self):
        received_at = self.cleaned_data["received_at"]
        return (
            timezone.make_aware(received_at)
            if timezone.is_naive(received_at)
            else received_at
        )


class ReceiptItemForm(_StyledForm):
    purchase_order_item = forms.ModelChoiceField(
        label="ردیف سفارش خرید", queryset=PurchaseOrderItem.objects.none()
    )
    quantity = forms.DecimalField(
        label="مقدار دریافتی", min_value=0.0001, decimal_places=4
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(
        self, *args: object, purchase_order: PurchaseOrder, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields[
            "purchase_order_item"
        ].queryset = purchase_order.items.select_related("material", "unit_of_measure")


class ReasonForm(_StyledForm):
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 3}))


class SupplierPortalInvitationForm(_StyledForm):
    invited_email = forms.EmailField(label="ایمیل نماینده تأمین‌کننده")
    expires_at = forms.DateTimeField(
        label="زمان انقضا", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def clean_expires_at(self):
        value = self.cleaned_data["expires_at"]
        return timezone.make_aware(value) if timezone.is_naive(value) else value


class SupplierPortalSubmissionForm(_StyledForm):
    upload = forms.FileField(label="اصل پیشنهاد (PDF یا DOCX)")
    # Optional client comparison metadata; intentionally not rendered by the portal.
    integrity_fingerprint = forms.CharField(required=False, widget=forms.HiddenInput())
    source_reference = forms.CharField(
        label="مرجع تأمین‌کننده", required=False, max_length=255
    )
    idempotency_key = forms.CharField(
        max_length=128,
        widget=forms.HiddenInput(),
    )


class SealedEvidenceUploadForm(_StyledForm):
    evidence_type = forms.ChoiceField(
        label="نوع فایل پیشنهاد",
        choices=(
            ("supplier_original", "اصل پیشنهاد تأمین‌کننده"),
            ("supplier_attachment", "پیوست تأمین‌کننده"),
        ),
    )
    evidence_slot = forms.CharField(
        label="نام کوتاه پیوست",
        required=False,
        max_length=80,
        help_text="برای پیوست تکمیلی، یک نام یکتا با حروف لاتین، عدد یا خط تیره وارد کنید؛ برای اصل پیشنهاد لازم نیست.",
    )
    upload = forms.FileField(label="فایل پیشنهاد یا پیوست")
    idempotency_key = forms.CharField(
        max_length=128, widget=forms.HiddenInput(), initial=lambda: uuid4().hex
    )
    expected_sha256 = forms.CharField(
        label="هش مورد انتظار SHA-256", required=False, max_length=64
    )
