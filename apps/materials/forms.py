from django import forms

from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from core.identifiers import canonicalize_upper_identifier


class UnitOfMeasureForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ["code", "name", "symbol", "category", "decimal_places"]  # noqa: RUF012

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class MaterialCategoryForm(forms.ModelForm):
    class Meta:
        model = MaterialCategory
        fields = ["code", "name", "parent"]  # noqa: RUF012

    def __init__(
        self, *args: object, organization_id: object, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = MaterialCategory.objects.filter(
            organization_id=organization_id, archived_at__isnull=True
        )

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["code", "name", "category", "unit_of_measure", "specifications"]  # noqa: RUF012

    def __init__(
        self, *args: object, organization_id: object, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            self.instance.organization_id = organization_id
        self.fields["category"].queryset = MaterialCategory.objects.filter(
            organization_id=organization_id, archived_at__isnull=True, is_active=True
        )
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization_id=organization_id, archived_at__isnull=True, is_active=True
        )

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])
