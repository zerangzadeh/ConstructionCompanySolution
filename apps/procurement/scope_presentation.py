"""Business-facing configuration adapters; persistence remains in the scope service."""

from decimal import Decimal
from uuid import uuid4

from django import forms

from apps.materials.models import UnitOfMeasure

from .commercial_scope_forms import source_signature
from .commercial_scope_services import source_lines


class RFQItemConfigurationForm(forms.Form):
    version_number = forms.IntegerField(widget=forms.HiddenInput())
    expected_revision = forms.IntegerField(widget=forms.HiddenInput())
    source_fingerprint = forms.CharField(widget=forms.HiddenInput())
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput(), initial=lambda: uuid4().hex, max_length=128
    )

    def __init__(self, *args, rfq, definition, **kwargs):
        super().__init__(*args, **kwargs)
        self.version_number = rfq.current_version_number + 1
        self.source_rows = list(source_lines(rfq, self.version_number))
        self.signature = source_signature(self.source_rows)
        self.initial.update(
            version_number=self.version_number,
            expected_revision=definition.revision_number if definition else 0,
            source_fingerprint=self.signature,
        )
        self.scopes = list(definition.payload["scopes"]) if definition else []
        by_item = {str(row.purchase_request_item_id): row for row in self.source_rows}
        configured = {
            member["purchase_request_item_id"]
            for scope in self.scopes
            for member in scope["lines"]
        }
        entries = [scope for scope in self.scopes if scope["scope_type"] == "line"]
        codes = {scope["scope_code"] for scope in self.scopes}
        for item_id, line in by_item.items():
            if item_id in configured:
                continue
            code = f"item-{item_id}"
            suffix = 0
            while code in codes:
                suffix += 1
                code = f"item-{item_id}-{suffix}"
            codes.add(code)
            entries.append(
                {
                    "scope_code": code,
                    "scope_type": "line",
                    "required_quantity": line.quantity,
                    "unit_of_measure_id": str(line.unit_of_measure_id),
                    "lines": [
                        {"purchase_request_item_id": item_id, "quantity": line.quantity}
                    ],
                    "independently_awardable": True,
                    "allows_split_award": False,
                    "allows_alternates": False,
                }
            )
        self.rows = []
        source_order = {item_id: index for index, item_id in enumerate(by_item)}
        entries.sort(
            key=lambda scope: (
                source_order.get(scope["lines"][0]["purchase_request_item_id"], -1),
                scope["scope_code"],
            )
        )
        for index, scope in enumerate(entries):
            line = by_item.get(scope["lines"][0]["purchase_request_item_id"])
            if line is None:
                # A stale definition cannot be silently pruned by this adapter.
                continue
            names = {}
            quantity = f"quantity_{index}"
            self.fields[quantity] = forms.DecimalField(
                label=f"مقدار استعلام · {line.material.name}",
                min_value=Decimal("0.0001"),
                max_value=line.quantity,
                max_digits=18,
                decimal_places=4,
                initial=format(Decimal(scope["required_quantity"]).normalize(), "f"),
                widget=forms.NumberInput(
                    attrs={"class": "erp-input w-full", "step": "0.0001"}
                ),
            )
            for flag, label in (
                ("independently_awardable", "انتخاب مستقل"),
                ("allows_split_award", "امکان تقسیم خرید"),
                ("allows_alternates", "پیشنهاد جایگزین مجاز"),
            ):
                name = f"{flag}_{index}"
                self.fields[name] = forms.TypedChoiceField(
                    label=label,
                    choices=(
                        [("yes", "انتخاب مستقل"), ("no", "بدون انتخاب مستقل")]
                        if flag == "independently_awardable"
                        else [("no", "خیر"), ("yes", "بله")]
                    ),
                    coerce=lambda value: value == "yes",
                    initial="yes" if scope[flag] else "no",
                    widget=forms.Select(attrs={"class": "erp-input w-full"}),
                )
                names[flag] = self[name]
            self.rows.append(
                dict(line=line, scope=scope, quantity=self[quantity], **names)
            )

    def clean(self):
        values = super().clean()
        if (
            values.get("version_number") != self.version_number
            or values.get("source_fingerprint") != self.signature
        ):
            raise forms.ValidationError(
                "اقلام یا نسخه استعلام تغییر کرده‌اند؛ صفحه را دوباره باز کنید."
            )
        if not self.rows:
            raise forms.ValidationError("ابتدا اقلام استعلام را انتخاب کنید.")
        updated = {row["scope"]["scope_code"] for row in self.rows}
        self.entries = [s for s in self.scopes if s["scope_code"] not in updated]
        for row in self.rows:
            flags = {
                flag: values.get(row[flag].name)
                for flag in (
                    "independently_awardable",
                    "allows_split_award",
                    "allows_alternates",
                )
            }
            if flags["allows_split_award"] and not flags["independently_awardable"]:
                self.add_error(
                    row["allows_split_award"].name,
                    "تقسیم خرید این قلم فقط با انتخاب مستقل مجاز است.",
                )
            amount = values.get(row["quantity"].name)
            self.entries.append(
                dict(
                    row["scope"],
                    required_quantity=amount,
                    lines=[
                        {
                            "purchase_request_item_id": str(
                                row["line"].purchase_request_item_id
                            ),
                            "quantity": amount,
                        }
                    ],
                    **flags,
                )
            )
        return values


def definition_entries(rfq, definition) -> list[dict]:
    """Resolve business identities only within the already-authorized RFQ."""
    if definition is None:
        return []
    members = {
        str(item.pk): item
        for item in rfq.purchase_request.items.select_related(
            "material", "unit_of_measure"
        )
    }
    units = dict(
        UnitOfMeasure.objects.filter(organization=rfq.organization).values_list(
            "pk", "name"
        )
    )
    units = {str(key): value for key, value in units.items()}
    source_quantities = {
        str(line.purchase_request_item_id): line.quantity
        for line in source_lines(rfq, definition.version_number)
    }
    result = []
    for scope in definition.payload["scopes"]:
        lines = [
            {
                "item": members.get(row["purchase_request_item_id"]),
                "quantity": row["quantity"],
                "source_quantity": source_quantities.get(
                    row["purchase_request_item_id"]
                ),
            }
            for row in scope["lines"]
        ]
        title = (
            scope["scope_code"]
            if scope["scope_type"] == "lot"
            else (lines[0]["item"].material.name if lines[0]["item"] else "قلم استعلام")
        )
        result.append(
            dict(
                scope,
                title=title,
                members=lines,
                unit_name=units.get(scope["unit_of_measure_id"], ""),
            )
        )
    return result


def configuration_context(rfq, definition, *, form=None) -> dict:
    current = definition
    if current is None and rfq.current_version_number:
        current = rfq.versions.get(
            version_number=rfq.current_version_number
        ).commercial_scope_definition
    entries = definition_entries(rfq, current)
    return {
        "configuration_form": form
        if form is not None
        else RFQItemConfigurationForm(rfq=rfq, definition=definition),
        "configuration_entries": entries,
        "purchase_groups": [entry for entry in entries if entry["scope_type"] == "lot"],
        "configuration_history": [
            {"definition": item, "entries": definition_entries(rfq, item)}
            for item in rfq.scope_definitions.order_by(
                "-version_number", "-revision_number"
            )
            if not current or item.pk != current.pk
        ],
    }
