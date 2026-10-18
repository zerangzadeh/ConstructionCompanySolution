from django import forms

from core.forms import JalaliDateMixin

from .models import (
    BusinessParty,
    PartyAliasType,
    PartyClassification,
    PartyClassificationAssignment,
    PartyClassificationKind,
    PartyRepresentative,
    PartyRepresentativeAuthority,
    PartyRestriction,
    PartyRestrictionEffect,
    PartyRestrictionScope,
)


class ScopedSourceForm(forms.Form):
    def __init__(self, *args, organization, party, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.party = party


class AliasForm(ScopedSourceForm):
    alias_type = forms.ChoiceField(
        label="نوع نام جایگزین", choices=PartyAliasType.choices
    )
    value = forms.CharField(label="نام یا شناسه جایگزین", max_length=255)
    reason = forms.CharField(
        label="دلیل ثبت", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )


class PartyChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        identity = obj.tax_identifier or str(obj.pk)[:8]
        return f"{obj.display_name} — {identity}"


class MergeForm(ScopedSourceForm):
    survivor = PartyChoice(label="طرف مرجع", queryset=BusinessParty.objects.none())
    reason = forms.CharField(
        label="دلیل ادغام", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )
    confirm = forms.BooleanField(
        label="طرف مبدأ و مرجع را بررسی کردم و ثبت سابقه ادغام را تأیید می‌کنم."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["survivor"].queryset = (
            BusinessParty.objects.filter(
                organization=self.organization,
                archived_at__isnull=True,
                merged_into__isnull=True,
            )
            .exclude(pk=self.party.pk)
            .order_by("display_name", "pk")
        )


class RestrictionForm(JalaliDateMixin, ScopedSourceForm):
    code = forms.CharField(label="کد محدودیت", max_length=80)
    effect = forms.ChoiceField(
        label="اثر ثبت‌شده", choices=PartyRestrictionEffect.choices
    )
    reason = forms.CharField(
        label="دلیل محدودیت", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )
    effective_from = forms.DateTimeField(
        label="شروع اثر",
        required=False,
        help_text="در صورت خالی بودن، زمان ثبت منبع استفاده می‌شود.",
    )
    effective_until = forms.DateTimeField(label="پایان اثر", required=False)


class ClassificationForm(ScopedSourceForm):
    kind = forms.ChoiceField(
        label="نوع واژگان", choices=PartyClassificationKind.choices
    )
    code = forms.CharField(label="کد واژگان", max_length=50)
    name = forms.CharField(label="نام واژگان", max_length=120)
    description = forms.CharField(
        label="توضیح", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class VocabularyChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_kind_display()} — {obj.name} — {obj.code}"


class ClassificationAssignmentForm(ScopedSourceForm):
    classification = VocabularyChoice(
        label="دسته یا برچسب", queryset=PartyClassification.objects.none()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classification"].queryset = PartyClassification.objects.filter(
            organization=self.organization, archived_at__isnull=True
        ).order_by("kind", "name", "pk")


class RepresentativeForm(JalaliDateMixin, ScopedSourceForm):
    authority = forms.ChoiceField(
        label="نوع اختیار", choices=PartyRepresentativeAuthority.choices
    )
    full_name = forms.CharField(label="نام نماینده", max_length=255)
    title = forms.CharField(label="سمت ثبت‌شده", max_length=120, required=False)
    evidence_reference = forms.CharField(label="مرجع مدرک اختیار", max_length=255)
    effective_from = forms.DateTimeField(
        label="شروع اثر",
        required=False,
        help_text="در صورت خالی بودن، زمان ثبت منبع استفاده می‌شود.",
    )
    effective_until = forms.DateTimeField(label="پایان اثر", required=False)


class RestrictionChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.code} — {obj.get_effect_display()}"


class ClassificationChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.classification.get_kind_display()} — {obj.classification.name} — {obj.classification.code}"


class RepresentativeChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.full_name} — {obj.get_authority_display()} — {obj.evidence_reference}"


class RevokeRestrictionForm(ScopedSourceForm):
    restriction = RestrictionChoice(
        label="محدودیت شرکتی", queryset=PartyRestriction.objects.none()
    )
    reason = forms.CharField(
        label="دلیل لغو", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["restriction"].queryset = PartyRestriction.objects.filter(
            organization=self.organization,
            party=self.party,
            scope=PartyRestrictionScope.TENANT,
            revoked_at__isnull=True,
        ).order_by("code", "pk")


class RevokeClassificationForm(ScopedSourceForm):
    assignment = ClassificationChoice(
        label="انتساب ثبت‌شده", queryset=PartyClassificationAssignment.objects.none()
    )
    reason = forms.CharField(
        label="دلیل لغو", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignment"].queryset = (
            PartyClassificationAssignment.objects.filter(
                organization=self.organization,
                party=self.party,
                revoked_at__isnull=True,
            )
            .select_related("classification")
            .order_by("classification__name", "pk")
        )


class RevokeRepresentativeForm(ScopedSourceForm):
    representative = RepresentativeChoice(
        label="نماینده ثبت‌شده", queryset=PartyRepresentative.objects.none()
    )
    reason = forms.CharField(
        label="دلیل لغو", max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["representative"].queryset = PartyRepresentative.objects.filter(
            organization=self.organization, party=self.party, revoked_at__isnull=True
        ).order_by("full_name", "pk")
