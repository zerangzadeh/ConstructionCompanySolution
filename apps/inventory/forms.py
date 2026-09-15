from django import forms
from django.utils import timezone

from apps.inventory.models import StockTransactionType, Warehouse
from apps.materials.models import Material
from apps.procurement.models import GoodsReceiptItem, GoodsReceiptStatus
from apps.projects.models import Project
from core.forms import JalaliDateMixin


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


class WarehouseForm(_StyledForm):
    code = forms.CharField(label="کد انبار", max_length=50)
    name = forms.CharField(label="نام انبار", max_length=255)
    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        required=False,
        empty_label="انبار مرکزی سازمان",
    )
    location = forms.CharField(
        label="محل انبار", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args: object, organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")


class StockTransactionForm(_StyledForm):
    transaction_number = forms.CharField(label="شماره تراکنش", max_length=80)
    transaction_type = forms.ChoiceField(
        label="نوع تراکنش",
        choices=[
            choice
            for choice in StockTransactionType.choices
            if choice[0] != StockTransactionType.REVERSAL
        ],
    )
    source_warehouse = forms.ModelChoiceField(
        label="انبار مبدأ",
        queryset=Warehouse.objects.none(),
        required=False,
        empty_label="بدون انبار مبدأ",
    )
    destination_warehouse = forms.ModelChoiceField(
        label="انبار مقصد",
        queryset=Warehouse.objects.none(),
        required=False,
        empty_label="بدون انبار مقصد",
    )
    material = forms.ModelChoiceField(label="مصالح", queryset=Material.objects.none())
    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        required=False,
        empty_label="بدون پروژه",
    )
    goods_receipt_item = forms.ModelChoiceField(
        label="ردیف رسید کالا",
        queryset=GoodsReceiptItem.objects.none(),
        required=False,
        empty_label="بدون ردیف رسید کالا",
    )
    quantity = forms.DecimalField(label="مقدار", min_value=0.0001, decimal_places=4)
    occurred_at = forms.DateTimeField(
        label="زمان وقوع", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    reference = forms.CharField(label="شماره مرجع", max_length=120, required=False)
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args: object, organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        active_warehouses = Warehouse.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")
        self.fields["source_warehouse"].queryset = active_warehouses
        self.fields["destination_warehouse"].queryset = active_warehouses
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
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")
        self.fields["goods_receipt_item"].queryset = (
            GoodsReceiptItem.objects.filter(
                organization=organization,
                goods_receipt__status=GoodsReceiptStatus.POSTED,
                stock_transactions__isnull=True,
            )
            .select_related("goods_receipt", "material")
            .order_by("goods_receipt__receipt_number")
        )

    def clean_occurred_at(self):
        occurred_at = self.cleaned_data["occurred_at"]
        return (
            timezone.make_aware(occurred_at)
            if timezone.is_naive(occurred_at)
            else occurred_at
        )

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("transaction_type")
        source = cleaned.get("source_warehouse")
        destination = cleaned.get("destination_warehouse")
        project = cleaned.get("project")
        receipt_item = cleaned.get("goods_receipt_item")
        if not kind:
            return cleaned
        rules = {
            StockTransactionType.RECEIPT: (False, True, False, True),
            StockTransactionType.ISSUE: (True, False, True, False),
            StockTransactionType.ADJUSTMENT_IN: (False, True, False, False),
            StockTransactionType.ADJUSTMENT_OUT: (True, False, False, False),
            StockTransactionType.TRANSFER: (True, True, False, False),
        }
        source_required, destination_required, project_required, receipt_required = (
            rules[kind]
        )
        if bool(source) != source_required:
            self.add_error(
                "source_warehouse", "انبار مبدأ برای این نوع تراکنش معتبر نیست."
            )
        if bool(destination) != destination_required:
            self.add_error(
                "destination_warehouse", "انبار مقصد برای این نوع تراکنش معتبر نیست."
            )
        if project_required and not project:
            self.add_error("project", "پروژه برای حواله خروج الزامی است.")
        if receipt_required and not receipt_item:
            self.add_error("goods_receipt_item", "ردیف رسید کالای ثبت‌شده الزامی است.")
        if not receipt_required and receipt_item:
            self.add_error(
                "goods_receipt_item", "این فیلد فقط برای ورود از خرید استفاده می‌شود."
            )
        if source and destination and source.pk == destination.pk:
            self.add_error(
                "destination_warehouse", "انبار مبدأ و مقصد باید متفاوت باشند."
            )
        if receipt_item:
            if (
                cleaned.get("material")
                and receipt_item.material_id != cleaned["material"].pk
            ):
                self.add_error("material", "مصالح باید با ردیف رسید کالا یکسان باشد.")
            if project and receipt_item.goods_receipt.project_id != project.pk:
                self.add_error("project", "پروژه باید با رسید کالا مطابقت داشته باشد.")
            cleaned["project"] = receipt_item.goods_receipt.project
        return cleaned


class ReversalForm(_StyledForm):
    reversal_number = forms.CharField(label="شماره تراکنش برگشت", max_length=80)
    reason = forms.CharField(
        label="دلیل برگشت", widget=forms.Textarea(attrs={"rows": 3})
    )
