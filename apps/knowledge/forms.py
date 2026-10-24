from django import forms

from core.forms import JalaliDateMixin

from .models import KnowledgeAuthority, KnowledgeSensitivity, ReuseType
from .reference_ui import visible_references


class ReferenceRowsWidget(forms.SelectMultiple):
    template_name = "knowledge/reference_rows.html"

    class Media:
        js = ("js/reference-rows.js",)

    def value_from_datadict(self, data, files, name):
        if data.get(f"{name}_rows_present"):
            values = (
                data.getlist(f"{name}_rows")
                if hasattr(data, "getlist")
                else data.get(f"{name}_rows", [])
            )
            if isinstance(values, str):
                values = [values]
            return "\n".join(value for value in values if value)
        return data.get(name, "")

    def format_value(self, value):
        return str(value or "").splitlines()

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["selected_rows"] = [
            forms.Select(choices=self.choices).render(
                f"{name}_rows",
                row,
                attrs={
                    "class": "w-full rounded border border-slate-300 p-2",
                    "aria-label": "منبع",
                },
            )
            for row in self.format_value(value)
        ]
        context["empty_row"] = forms.Select(choices=self.choices).render(
            f"{name}_rows",
            "",
            attrs={
                "class": "w-full rounded border border-slate-300 p-2",
                "aria-label": "منبع",
            },
        )
        return context


class CandidateForm(forms.Form):
    title = forms.CharField(label="عنوان", max_length=240)
    body = forms.CharField(label="متن راهنما", widget=forms.Textarea(attrs={"rows": 8}))
    knowledge_type = forms.ChoiceField(
        label="نوع",
        choices=(
            ("lesson_learned", "درس‌آموخته"),
            ("best_practice", "روش برتر"),
            ("technical_note", "یادداشت فنی"),
            ("procedure", "رویه راهنما"),
            ("knowledge_article", "مقاله دانشی"),
            ("case_study", "مطالعه موردی"),
        ),
    )
    authority_classification = forms.ChoiceField(
        label="سطح اختیار", choices=KnowledgeAuthority.choices
    )
    sensitivity = forms.ChoiceField(
        label="حساسیت", choices=KnowledgeSensitivity.choices
    )
    audience = forms.CharField(label="مخاطب", max_length=80)
    category_code = forms.CharField(label="دسته", max_length=80)
    tags = forms.CharField(label="برچسب‌ها", required=False)

    def clean_tags(self):
        return [
            value.strip()
            for value in self.cleaned_data["tags"].split(",")
            if value.strip()
        ]


class SourceForm(forms.Form):
    source_type = forms.ChoiceField(
        label="نوع منبع",
        choices=(
            ("field_observation", "مشاهده میدانی"),
            ("inspection", "بازرسی"),
            ("inspection_finding", "یافته بازرسی"),
            ("nonconformance", "عدم انطباق"),
            ("capa_action", "CAPA"),
            ("partner_evaluation", "ارزیابی همکار"),
            ("support_case", "مورد پشتیبانی"),
        ),
    )
    source_id = forms.UUIDField(label="شناسه منبع")
    citation_purpose = forms.CharField(label="هدف استناد", max_length=160)

    def __init__(self, *args, organization=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.references = None
        if organization is not None and actor is not None:
            choices, self.references = visible_references(
                organization=organization, actor=actor
            )
            self.fields["reference"] = forms.ChoiceField(
                label="منبع قابل مشاهده",
                choices=[("", "انتخاب منبع"), *choices],
                required=False,
            )
            for name in ("source_type", "source_id"):
                self.fields[name].required = False
                self.fields[name].widget = forms.HiddenInput()
            self.order_fields(
                ("reference", "citation_purpose", "source_type", "source_id")
            )

    def clean(self):
        data = super().clean()
        if self.references is not None:
            reference = self.references.get(data.pop("reference", ""))
            if reference:
                data.update(source_type=reference["type"], source_id=reference["id"])
            elif not data.get("source_type") or not data.get("source_id"):
                self.add_error("reference", "منبع مجاز را انتخاب کنید.")
        return data


class ReviewForm(forms.Form):
    outcome = forms.ChoiceField(
        label="نتیجه",
        choices=(
            ("changes_requested", "بازگشت برای اصلاح"),
            ("recommended", "توصیه برای انتشار"),
            ("rejected", "رد"),
        ),
    )
    reason = forms.CharField(
        label="دلیل", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    expected_status = forms.CharField(widget=forms.HiddenInput)


class RecurrenceForm(JalaliDateMixin, forms.Form):
    recurrence_key = forms.CharField(label="کلید تکرار", max_length=120)
    scope_description = forms.CharField(label="دامنه", max_length=240)
    period_start = forms.DateField(label="شروع دوره")
    period_end = forms.DateField(label="پایان دوره")
    sources = forms.CharField(label="منابع", help_text="هر خط: type,uuid")

    def __init__(self, *args, organization=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_sources = None
        if organization is not None and actor is not None:
            groups, references = visible_references(
                organization=organization, actor=actor
            )
            self.allowed_sources = {
                f"{value['type']},{value['id']}" for value in references.values()
            }
            choices = [("", "انتخاب منبع")]
            for label, group in groups:
                choices.append(
                    (
                        label,
                        [
                            (f"{references[key]['type']},{references[key]['id']}", text)
                            for key, text in group
                        ],
                    )
                )
            self.fields["sources"].widget = ReferenceRowsWidget(choices=choices)
            self.fields[
                "sources"
            ].help_text = "هر منبع را در یک ردیف انتخاب کنید؛ فقط منابع واجد شرایط و قابل مشاهده در فضای منبع نمایش داده می‌شوند."

    def clean_sources(self):
        values = []
        for line in self.cleaned_data["sources"].splitlines():
            if not line.strip():
                continue
            if (
                self.allowed_sources is not None
                and self.data.get("sources_rows_present")
                and line.strip() not in self.allowed_sources
            ):
                raise forms.ValidationError("منبع انتخاب‌شده دیگر در فهرست مجاز نیست.")
            try:
                source_type, source_id = [part.strip() for part in line.split(",", 1)]
            except ValueError as exc:
                raise forms.ValidationError("هر منبع باید type,uuid باشد.") from exc
            values.append({"source_type": source_type, "source_id": source_id})
        return values


class ReuseForm(forms.Form):
    reuse_type = forms.ChoiceField(label="نوع استفاده", choices=ReuseType.choices)
    consumer_type = forms.CharField(label="نوع مصرف‌کننده", max_length=80)
    consumer_id = forms.UUIDField(label="شناسه مصرف‌کننده")
    consumer_version = forms.CharField(label="نسخه مصرف‌کننده", max_length=80)
    purpose = forms.CharField(label="هدف", max_length=240)

    def __init__(self, *args, organization=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.references = None
        if organization is not None and actor is not None:
            choices, self.references = visible_references(
                organization=organization, actor=actor, sources=False
            )
            self.fields["reference"] = forms.ChoiceField(
                label="رکورد مصرف‌کننده قابل مشاهده",
                choices=[("", "انتخاب رکورد"), *choices],
                required=False,
            )
            for name in ("consumer_type", "consumer_id", "consumer_version"):
                self.fields[name].required = False
                self.fields[name].widget = forms.HiddenInput()
            self.order_fields(
                (
                    "reuse_type",
                    "reference",
                    "purpose",
                    "consumer_type",
                    "consumer_id",
                    "consumer_version",
                )
            )

    def clean(self):
        data = super().clean()
        if self.references is not None:
            reference = self.references.get(data.pop("reference", ""))
            if reference:
                data.update(
                    consumer_type=reference["type"],
                    consumer_id=reference["id"],
                    consumer_version=reference["version"],
                )
            elif not all(
                data.get(name)
                for name in ("consumer_type", "consumer_id", "consumer_version")
            ):
                self.add_error("reference", "رکورد مصرف‌کننده مجاز را انتخاب کنید.")
        return data


class PublicationCorrectionForm(forms.Form):
    title = forms.CharField(label="عنوان نسخه اصلاحی", max_length=240)
    body = forms.CharField(label="متن اصلاحی", widget=forms.Textarea(attrs={"rows": 8}))
    reason = forms.CharField(
        label="دلیل اصلاح", widget=forms.Textarea(attrs={"rows": 3})
    )


class PromotionRequestForm(forms.Form):
    title = forms.CharField(label="عنوان پالایش‌شده", max_length=240)
    body = forms.CharField(
        label="متن پالایش‌شده و بی‌نام", widget=forms.Textarea(attrs={"rows": 8})
    )
    audience = forms.CharField(label="مخاطب سکوی مشترک", max_length=80)
    category_code = forms.CharField(label="دسته سکوی مشترک", max_length=80)
    anonymization_statement = forms.CharField(
        label="شرح حذف و بی‌نام‌سازی اطلاعات شرکت",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class RecurrenceCorrectionForm(RecurrenceForm):
    disposition = forms.ChoiceField(
        label="نوع اصلاح",
        choices=(("replace", "جایگزینی"), ("invalidate", "بی‌اعتبارسازی")),
    )
    reason = forms.CharField(
        label="دلیل اصلاح", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "recurrence_key",
            "scope_description",
            "period_start",
            "period_end",
            "sources",
        ):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("disposition") == "replace" and not all(
            cleaned.get(name)
            for name in (
                "recurrence_key",
                "scope_description",
                "period_start",
                "period_end",
                "sources",
            )
        ):
            raise forms.ValidationError(
                "برای جایگزینی، همه مشخصات شاهد جدید الزامی است."
            )
        return cleaned


class ReuseCorrectionForm(forms.Form):
    disposition = forms.ChoiceField(
        label="نوع اصلاح",
        choices=(("reverse", "برگشت"), ("replace", "جایگزینی")),
    )
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 2}))
    purpose = forms.CharField(label="هدف اصلاح‌شده", max_length=240, required=False)
    consumer_version = forms.CharField(
        label="نسخه مصرف‌کننده اصلاح‌شده", max_length=80, required=False
    )
