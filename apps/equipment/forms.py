from django import forms

from apps.equipment.models import (
    Equipment,
    EquipmentOwnershipType,
    EquipmentStatus,
    MaintenanceType,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite
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


class EquipmentForm(_StyledForm):
    code = forms.CharField(label="کد تجهیز", max_length=50)
    name = forms.CharField(label="نام تجهیز", max_length=255)
    category = forms.CharField(label="دسته تجهیز", max_length=120)
    ownership_type = forms.ChoiceField(
        label="نوع مالکیت", choices=EquipmentOwnershipType.choices
    )
    manufacturer = forms.CharField(label="سازنده", max_length=120, required=False)
    model = forms.CharField(label="مدل", max_length=120, required=False)
    serial_number = forms.CharField(label="شماره سریال", max_length=120, required=False)
    registration_number = forms.CharField(
        label="شماره پلاک یا ثبت", max_length=64, required=False
    )
    acquired_on = forms.DateField(
        label="تاریخ تملک یا شروع اجاره",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )


class EquipmentAssignmentForm(_StyledForm):
    equipment = forms.ModelChoiceField(label="تجهیز", queryset=Equipment.objects.none())
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(
        label="کارگاه",
        queryset=ProjectSite.objects.none(),
        required=False,
        empty_label="بدون کارگاه",
    )
    start_date = forms.DateField(
        label="تاریخ شروع", widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        label="تاریخ پایان",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    purpose = forms.CharField(label="هدف تخصیص", max_length=255, required=False)
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args: object, organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["equipment"].queryset = Equipment.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("name")
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")
        self.fields["site"].queryset = (
            ProjectSite.objects.filter(
                organization=organization,
                is_active=True,
                project__deleted_at__isnull=True,
            )
            .select_related("project")
            .order_by("project__name", "name")
        )

    def clean(self):
        cleaned = super().clean()
        site, project = cleaned.get("site"), cleaned.get("project")
        if site and project and site.project_id != project.pk:
            self.add_error("site", "کارگاه باید متعلق به پروژه انتخاب‌شده باشد.")
        return cleaned


class MaintenanceRecordForm(_StyledForm):
    equipment = forms.ModelChoiceField(label="تجهیز", queryset=Equipment.objects.none())
    record_number = forms.CharField(label="شماره سرویس", max_length=50)
    maintenance_type = forms.ChoiceField(
        label="نوع نگهداری", choices=MaintenanceType.choices
    )
    summary = forms.CharField(label="عنوان سرویس یا تعمیر", max_length=255)
    scheduled_date = forms.DateField(
        label="تاریخ برنامه‌ریزی‌شده", widget=forms.DateInput(attrs={"type": "date"})
    )
    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        required=False,
        empty_label="بدون پروژه",
    )
    site = forms.ModelChoiceField(
        label="کارگاه",
        queryset=ProjectSite.objects.none(),
        required=False,
        empty_label="بدون کارگاه",
    )
    provider = forms.ModelChoiceField(
        label="ارائه‌دهنده خدمت",
        queryset=BusinessParty.objects.none(),
        required=False,
        empty_label="بدون ارائه‌دهنده",
    )
    description = forms.CharField(
        label="شرح کار", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    cost = forms.DecimalField(
        label="هزینه", required=False, min_value=0, decimal_places=2
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args: object, organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["equipment"].queryset = Equipment.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("name")
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).order_by("name")
        self.fields["site"].queryset = (
            ProjectSite.objects.filter(
                organization=organization,
                is_active=True,
                project__deleted_at__isnull=True,
            )
            .select_related("project")
            .order_by("project__name", "name")
        )
        self.fields["provider"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")

    def clean(self):
        cleaned = super().clean()
        site, project = cleaned.get("site"), cleaned.get("project")
        if site and (not project or site.project_id != project.pk):
            self.add_error("site", "کارگاه باید متعلق به پروژه انتخاب‌شده باشد.")
        return cleaned


class StatusTransitionForm(_StyledForm):
    target_status = forms.ChoiceField(label="وضعیت جدید", choices=())
    effective_date = forms.DateField(
        label="تاریخ اثر", widget=forms.DateInput(attrs={"type": "date"})
    )
    cost = forms.DecimalField(
        label="هزینه نهایی", required=False, min_value=0, decimal_places=2
    )

    def __init__(
        self, *args: object, choices=(), include_cost: bool = False, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["target_status"].choices = choices
        if not include_cost:
            self.fields.pop("cost")


class EquipmentStatusForm(_StyledForm):
    target_status = forms.ChoiceField(
        label="وضعیت جدید",
        choices=[
            (EquipmentStatus.INACTIVE, EquipmentStatus.INACTIVE.label),
            (EquipmentStatus.RETIRED, EquipmentStatus.RETIRED.label),
            (EquipmentStatus.AVAILABLE, EquipmentStatus.AVAILABLE.label),
        ],
    )
