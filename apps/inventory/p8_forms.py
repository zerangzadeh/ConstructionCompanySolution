from django import forms

from apps.inventory.forms import _StyledForm
from apps.inventory.models import (
    InventoryLot,
    InventorySerial,
    TransferExceptionCode,
    Warehouse,
    WarehouseBin,
)
from apps.materials.models import Material
from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.projects.models import Project


class ReservationCreateForm(_StyledForm):
    reservation_number = forms.CharField(label="شماره رزرو", max_length=80)
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    warehouse = forms.ModelChoiceField(label="انبار", queryset=Warehouse.objects.none())
    material = forms.ModelChoiceField(label="مصالح", queryset=Material.objects.none())
    quantity = forms.DecimalField(label="مقدار", min_value=0.0001, decimal_places=4)
    need_by = forms.DateField(
        label="تاریخ نیاز",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    bin = forms.ModelChoiceField(
        label="مکان", queryset=WarehouseBin.objects.none(), required=False
    )
    lot = forms.ModelChoiceField(
        label="بچ", queryset=InventoryLot.objects.none(), required=False
    )
    serial = forms.ModelChoiceField(
        label="سریال", queryset=InventorySerial.objects.none(), required=False
    )

    def __init__(self, *args: object, organization, user, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=user, organization=organization)
        self.fields["project"].queryset = scope_queryset(
            queryset=Project.objects.filter(
                organization=organization, deleted_at__isnull=True
            ),
            membership=membership,
            project_lookup="pk",
        ).order_by("name")
        self.fields["warehouse"].queryset = scope_queryset(
            queryset=Warehouse.objects.filter(
                organization=organization, is_active=True, archived_at__isnull=True
            ),
            membership=membership,
            project_lookup="project_id",
        ).order_by("name")
        self.fields["material"].queryset = Material.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")
        self.fields["bin"].queryset = scope_queryset(
            queryset=WarehouseBin.objects.filter(
                organization=organization, is_active=True
            ),
            membership=membership,
            project_lookup="warehouse__project_id",
        ).order_by("warehouse__name", "code")
        self.fields["lot"].queryset = InventoryLot.objects.filter(
            organization=organization
        ).order_by("material__name", "lot_code")
        self.fields["serial"].queryset = InventorySerial.objects.filter(
            organization=organization
        ).order_by("material__name", "serial_number")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("lot") and cleaned.get("serial"):
            self.add_error("serial", "بچ و سریال هم‌زمان قابل انتخاب نیستند.")
        return cleaned


class InventoryCountCreateForm(_StyledForm):
    count_number = forms.CharField(label="شماره شمارش", max_length=80)
    warehouse = forms.ModelChoiceField(label="انبار", queryset=Warehouse.objects.none())
    bin = forms.ModelChoiceField(
        label="مکان اختیاری", queryset=WarehouseBin.objects.none(), required=False
    )

    def __init__(self, *args: object, organization, user, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=user, organization=organization)
        self.fields["warehouse"].queryset = scope_queryset(
            queryset=Warehouse.objects.filter(
                organization=organization, is_active=True, archived_at__isnull=True
            ),
            membership=membership,
            project_lookup="project_id",
        ).order_by("name")
        self.fields["bin"].queryset = scope_queryset(
            queryset=WarehouseBin.objects.filter(
                organization=organization, is_active=True
            ),
            membership=membership,
            project_lookup="warehouse__project_id",
        ).order_by("warehouse__name", "code")

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("bin")
            and cleaned.get("warehouse")
            and cleaned["bin"].warehouse_id != cleaned["warehouse"].pk
        ):
            self.add_error("bin", "مکان باید متعلق به انبار انتخاب‌شده باشد.")
        return cleaned


class InventoryTransferCreateForm(_StyledForm):
    transfer_number = forms.CharField(label="شماره انتقال", max_length=80)
    source_warehouse = forms.ModelChoiceField(
        label="انبار مبدأ", queryset=Warehouse.objects.none()
    )
    destination_warehouse = forms.ModelChoiceField(
        label="انبار مقصد", queryset=Warehouse.objects.none()
    )
    material = forms.ModelChoiceField(label="مصالح", queryset=Material.objects.none())
    quantity = forms.DecimalField(label="مقدار", min_value=0.0001, decimal_places=4)
    source_bin = forms.ModelChoiceField(
        label="مکان مبدأ", queryset=WarehouseBin.objects.none(), required=False
    )
    destination_bin = forms.ModelChoiceField(
        label="مکان مقصد", queryset=WarehouseBin.objects.none(), required=False
    )
    lot = forms.ModelChoiceField(
        label="بچ", queryset=InventoryLot.objects.none(), required=False
    )
    serial = forms.ModelChoiceField(
        label="سریال", queryset=InventorySerial.objects.none(), required=False
    )

    def __init__(self, *args: object, organization, user, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=user, organization=organization)
        warehouses = scope_queryset(
            queryset=Warehouse.objects.filter(
                organization=organization, is_active=True, archived_at__isnull=True
            ),
            membership=membership,
            project_lookup="project_id",
        ).order_by("name")
        self.fields["source_warehouse"].queryset = warehouses
        self.fields["destination_warehouse"].queryset = warehouses
        self.fields["material"].queryset = Material.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")
        bins = scope_queryset(
            queryset=WarehouseBin.objects.filter(
                organization=organization, is_active=True
            ),
            membership=membership,
            project_lookup="warehouse__project_id",
        ).order_by("warehouse__name", "code")
        self.fields["source_bin"].queryset = bins
        self.fields["destination_bin"].queryset = bins
        self.fields["lot"].queryset = InventoryLot.objects.filter(
            organization=organization
        ).order_by("material__name", "lot_code")
        self.fields["serial"].queryset = InventorySerial.objects.filter(
            organization=organization
        ).order_by("material__name", "serial_number")

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source_warehouse")
        destination = cleaned.get("destination_warehouse")
        if source and destination and source.pk == destination.pk:
            self.add_error("destination_warehouse", "انبار مقصد باید متفاوت باشد.")
        for field, warehouse in (
            ("source_bin", source),
            ("destination_bin", destination),
        ):
            if (
                cleaned.get(field)
                and warehouse
                and cleaned[field].warehouse_id != warehouse.pk
            ):
                self.add_error(field, "مکان باید متعلق به انبار متناظر باشد.")
        if cleaned.get("lot") and cleaned.get("serial"):
            self.add_error("serial", "بچ و سریال هم‌زمان قابل انتخاب نیستند.")
        return cleaned


class TransferAcceptanceForm(_StyledForm):
    accepted_quantity = forms.DecimalField(
        label="مقدار پذیرفته", min_value=0, decimal_places=4
    )
    exception_code = forms.ChoiceField(
        label="نوع مغایرت", choices=TransferExceptionCode.choices
    )
    exception_reason = forms.CharField(
        label="شرح مغایرت", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
