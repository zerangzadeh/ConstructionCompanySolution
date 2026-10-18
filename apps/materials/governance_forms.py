"""Closed UI inputs for existing Materials services; no new domain semantics."""

from django import forms

from core.forms import JalaliDateMixin

from . import models as m


class ScopedForm(JalaliDateMixin, forms.Form):
    def __init__(self, *args, organization, material=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ModelChoiceField):
                model = field.queryset.model
                lookup = (
                    "definition__organization"
                    if model is m.MaterialAttributeDefinitionVersion
                    else "organization"
                )
                field.queryset = model.objects.filter(**{lookup: organization})
                if model is m.Material:
                    field.queryset = field.queryset.filter(
                        is_active=True, archived_at__isnull=True
                    ).exclude(pk=material.pk if material else None)
                if model is m.MaterialTechnicalApproval:
                    field.queryset = field.queryset.filter(material=material)
                if model is m.MaterialAttributeDefinition and material:
                    field.queryset = field.queryset.filter(category=material.category)
                if model is m.MaterialAttributeDefinitionVersion and material:
                    field.queryset = field.queryset.filter(
                        definition__category=material.category
                    )


class AliasForm(ScopedForm):
    code = forms.CharField(label="کد جایگزین", max_length=50)
    label = forms.CharField(label="برچسب", max_length=255, required=False)
    reason = forms.CharField(label="دلیل ثبت", widget=forms.Textarea)


class RelationshipForm(ScopedForm):
    candidate = forms.ModelChoiceField(label="مصالح مرتبط", queryset=m.Material.objects.none())
    relationship_type = forms.ChoiceField(label="نوع رابطه", choices=m.MaterialRelationshipType.choices)
    reason = forms.CharField(label="دلیل فنی", widget=forms.Textarea)


class RevisionForm(ScopedForm):
    # The source's existing tenant-master operation creates an organization-wide
    # revision when no project is supplied; this UI does not infer a selected project.
    confirm = forms.BooleanField(label="ایجاد نسخه بررسی فنی در دامنه شرکت را تأیید می‌کنم.")


class TransitionForm(ScopedForm):
    approval = forms.ModelChoiceField(label="نسخه بررسی فنی", queryset=m.MaterialTechnicalApproval.objects.none())
    reason = forms.CharField(label="دلیل", required=False, widget=forms.Textarea)


class AttributeValueForm(ScopedForm):
    definition = forms.ModelChoiceField(label="تعریف ویژگی", queryset=m.MaterialAttributeDefinition.objects.none())
    definition_version = forms.ModelChoiceField(label="نسخه تعریف ویژگی", queryset=m.MaterialAttributeDefinitionVersion.objects.none())
    value = forms.JSONField(label="مقدار مطابق نوع نسخه", help_text='متن: "A4"؛ عدد: 12؛ بله/خیر: true یا false')
    source_reference = forms.CharField(label="مرجع مدرک", max_length=255, required=False)


class FamilyForm(ScopedForm):
    base_unit = forms.ModelChoiceField(label="واحد مبنا", queryset=m.UnitOfMeasure.objects.none())
    code = forms.CharField(label="کد خانواده", max_length=40)
    name = forms.CharField(label="نام خانواده", max_length=120)
    dimension = forms.ChoiceField(label="بعد", choices=m.UnitDimension.choices)


class FamilyAssignmentForm(ScopedForm):
    unit = forms.ModelChoiceField(label="واحد", queryset=m.UnitOfMeasure.objects.none())
    family = forms.ModelChoiceField(label="خانواده", queryset=m.UnitFamily.objects.none())


class EffectiveForm(ScopedForm):
    effective_from = forms.DateTimeField(label="شروع اعتبار")
    effective_until = forms.DateTimeField(label="پایان اعتبار", required=False)


class ConversionVersionForm(EffectiveForm):
    unit = forms.ModelChoiceField(label="واحد", queryset=m.UnitOfMeasure.objects.none())
    factor_to_base = forms.DecimalField(label="ضریب به واحد مبنا", max_digits=30, decimal_places=18)
    source_reference = forms.CharField(label="مرجع ضریب", max_length=255)


class RoundingForm(EffectiveForm):
    code = forms.CharField(label="کد سیاست", max_length=40)
    scale = forms.IntegerField(label="تعداد اعشار", min_value=0, max_value=12)
    mode = forms.ChoiceField(label="روش گرد کردن", choices=m.QuantityRoundingMode.choices)


class DefinitionForm(ScopedForm):
    category = forms.ModelChoiceField(label="دسته‌بندی مصالح", queryset=m.MaterialCategory.objects.none())
    code = forms.CharField(label="کد ویژگی", max_length=50)
    name = forms.CharField(label="نام ویژگی", max_length=150)
    value_type = forms.ChoiceField(label="نوع مقدار", choices=m.MaterialAttributeValueType.choices)
    allowed_operators = forms.MultipleChoiceField(label="عملگرهای مجاز", choices=m.MaterialAttributeOperator.choices)
    choice_values = forms.CharField(label="گزینه‌های بسته؛ هر سطر یک گزینه", required=False, widget=forms.Textarea)
    effective_from = forms.DateTimeField(label="شروع اعتبار")

    def clean_choice_values(self):
        return [line.strip() for line in self.cleaned_data["choice_values"].splitlines() if line.strip()]


class DefinitionVersionForm(DefinitionForm):
    category = None
    code = None
    name = None
    definition = forms.ModelChoiceField(label="تعریف ویژگی", queryset=m.MaterialAttributeDefinition.objects.none())
    effective_until = forms.DateTimeField(label="پایان اعتبار", required=False)
