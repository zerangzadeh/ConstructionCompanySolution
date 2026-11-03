"""Business-labelled inputs for explicit scope definition and existing addenda."""

from decimal import Decimal
from uuid import uuid4

from django import forms

from apps.materials.models import UnitOfMeasure
from core.forms import JalaliDateMixin

from .commercial_scope_services import fingerprint, source_lines
from .rfq_forms import BusinessChoiceField


def source_signature(lines):
    rows = [
        [
            str(row.purchase_request_item_id),
            str(row.material_id),
            str(row.unit_of_measure_id),
            f"{row.quantity:.4f}",
            row.description,
            row.sort_order,
        ]
        for row in lines
    ]
    return fingerprint(sorted(rows, key=lambda row: row[0]))


class ScopeDefinitionForm(forms.Form):
    scope_type = forms.ChoiceField(
        label="نحوه مقایسه اقلام",
        choices=[("", "انتخاب کنید"), ("line", "یک قلم"), ("lot", "گروه خرید")],
    )
    scope_code = forms.CharField(label="نام گروه خرید", max_length=80)
    required_quantity = forms.DecimalField(
        label="تعداد / مقدار گروه خرید",
        required=False,
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        help_text="مبنای مقایسه کل گروه را با واحد آن مشخص کنید؛ مقدار هر قلم جداگانه نمایش داده می‌شود.",
    )
    unit_of_measure = BusinessChoiceField(
        label="واحد گروه خرید", queryset=UnitOfMeasure.objects.none(), required=False
    )
    version_number = forms.IntegerField(widget=forms.HiddenInput())
    expected_revision = forms.IntegerField(widget=forms.HiddenInput())
    source_fingerprint = forms.CharField(widget=forms.HiddenInput())
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput(), initial=lambda: uuid4().hex, max_length=128
    )

    def __init__(self, *args, rfq, definition, edit_code=None, **kwargs):
        self.rfq = rfq
        self.definition = definition
        self.version_number = rfq.current_version_number + 1
        super().__init__(*args, **kwargs)
        self.source_rows = list(source_lines(rfq, self.version_number))
        self.signature = source_signature(self.source_rows)
        self.initial.update(
            version_number=self.version_number,
            expected_revision=definition.revision_number if definition else 0,
            source_fingerprint=self.signature,
        )
        self.edit_entry = (
            next(
                (
                    entry
                    for entry in definition.payload["scopes"]
                    if entry["scope_code"] == edit_code
                ),
                None,
            )
            if definition
            else None
        )
        if self.edit_entry:
            self.initial.update(self.edit_entry)
            self.initial["unit_of_measure"] = self.edit_entry["unit_of_measure_id"]
        else:
            self.initial["scope_type"] = "lot"
        self.fields["scope_type"].widget = forms.HiddenInput()
        self.is_line = bool(self.edit_entry and self.edit_entry["scope_type"] == "line")
        if self.is_line:
            self.fields["scope_code"].widget = forms.HiddenInput()
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=rfq.organization,
            is_active=True,
            archived_at__isnull=True,
        ).order_by("name")
        self.fields["unit_of_measure"].empty_label = "انتخاب واحد گروه"
        self.fields["unit_of_measure"].label_from_instance = lambda unit: (
            f"{unit.name} · {unit.symbol}"
        )
        self.members = []
        chosen = (
            {
                entry["purchase_request_item_id"]: entry["quantity"]
                for entry in self.edit_entry["lines"]
            }
            if self.edit_entry
            else {}
        )
        for index, row in enumerate(self.source_rows):
            name = f"member_{index}"
            selector = f"select_{index}"
            self.fields[selector] = forms.BooleanField(
                label=f"انتخاب {row.material.name}",
                required=False,
                initial=str(row.purchase_request_item_id) in chosen,
            )
            self.fields[name] = forms.DecimalField(
                label=f"مقدار استعلام · {row.material.name}",
                required=False,
                decimal_places=4,
                max_digits=18,
                min_value=Decimal("0.0001"),
                max_value=row.quantity,
                initial=format(
                    Decimal(
                        chosen.get(str(row.purchase_request_item_id), row.quantity)
                    ).normalize(),
                    "f",
                ),
                help_text=f"حداکثر {row.quantity} {row.unit_of_measure.name}",
            )
            self.members.append(
                {"line": row, "field": self[name], "select": self[selector]}
            )
        for name, label in (
            ("independently_awardable", "انتخاب مستقل برای این گروه / قلم"),
            ("allows_split_award", "امکان تقسیم خرید بین چند تأمین‌کننده"),
            ("allows_alternates", "پذیرش پیشنهاد جایگزین"),
        ):
            self.fields[name] = forms.TypedChoiceField(
                label=label,
                choices=[("", "صریحاً انتخاب کنید"), ("yes", "بله"), ("no", "خیر")],
                coerce=lambda value: value == "yes",
                initial=("yes" if self.edit_entry[name] else "no")
                if self.edit_entry
                else ("yes" if name == "independently_awardable" else "no"),
            )
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "erp-input w-full")

    def clean(self):
        values = super().clean()
        if (
            values.get("version_number") != self.version_number
            or values.get("source_fingerprint") != self.signature
        ):
            raise forms.ValidationError(
                "اقلام یا نسخه استعلام تغییر کرده‌اند؛ صفحه را دوباره باز کنید."
            )
        selected = [
            {
                "purchase_request_item_id": str(
                    member["line"].purchase_request_item_id
                ),
                "quantity": values[member["field"].name],
            }
            for member in self.members
            if values.get(member["field"].name) is not None
            and (not self.data.get("selection_ui") or values.get(member["select"].name))
        ]
        kind = values.get("scope_type")
        if not selected or (kind == "line" and len(selected) != 1):
            raise forms.ValidationError(
                "برای یک قلم، همان قلم و برای گروه خرید، اقلام عضو را انتخاب کنید."
            )
        if kind == "lot":
            if not values.get("required_quantity"):
                self.add_error(
                    "required_quantity", "تعداد / مقدار گروه خرید را وارد کنید."
                )
            if not values.get("unit_of_measure"):
                self.add_error("unit_of_measure", "واحد گروه خرید را انتخاب کنید.")
        if (
            kind == "line"
            and values.get("allows_split_award")
            and not values.get("independently_awardable")
        ):
            self.add_error(
                "allows_split_award", "تقسیم ردیف فقط با انتخاب مستقل مجاز است."
            )
        if not self.errors:
            entry = {
                key: values[key]
                for key in (
                    "scope_type",
                    "scope_code",
                    "independently_awardable",
                    "allows_split_award",
                    "allows_alternates",
                )
            }
            entry.update(
                lines=selected,
                required_quantity=selected[0]["quantity"]
                if kind == "line"
                else values["required_quantity"],
                unit_of_measure_id=str(values["unit_of_measure"].pk)
                if kind == "lot"
                else "",
            )
            self.entry = entry
        return values


class RFQAddendumForm(JalaliDateMixin, forms.Form):
    closing_at = forms.DateTimeField(label="مهلت دریافت نسخه جدید")
    earliest_opening_at = forms.DateTimeField(label="زمان مجاز گشایش نسخه جدید")
    terms = forms.CharField(
        label="شرایط نسخه جدید",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput(), initial=lambda: uuid4().hex, max_length=128
    )

    def __init__(self, *args, rfq, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update(
                closing_at=rfq.closing_at,
                earliest_opening_at=rfq.earliest_opening_at,
                terms=rfq.terms,
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
