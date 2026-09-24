from datetime import date, datetime, timezone

from django import forms

from core.forms import JalaliDateInput, JalaliDateMixin, JalaliDateTimeInput


class SampleDateForm(JalaliDateMixin, forms.Form):
    business_date = forms.DateField()
    recorded_at = forms.DateTimeField()


def test_date_widgets_use_jalali_mask() -> None:
    form = SampleDateForm(initial={"business_date": date(2026, 3, 21)})

    assert isinstance(form.fields["business_date"].widget, JalaliDateInput)
    assert form.fields["business_date"].widget.attrs["data-input-mask"] == "####/##/##"
    assert 'value="1405/01/01"' in form["business_date"].as_widget()


def test_jalali_values_are_converted_and_validated() -> None:
    valid = SampleDateForm(
        data={"business_date": "۱۴۰۵/۰۱/۰۱", "recorded_at": "۱۴۰۵/۰۱/۰۱ ۱۲:۳۰"}
    )

    assert valid.is_valid()
    assert valid.cleaned_data["business_date"] == date(2026, 3, 21)
    assert valid.cleaned_data["recorded_at"] == datetime(
        2026, 3, 21, 12, 30, tzinfo=timezone.utc
    )

    invalid = SampleDateForm(
        data={"business_date": "۱۴۰۵/۰۱/۳۲", "recorded_at": "۱۴۰۵/۱۳/۰۱ ۱۲:۳۰"}
    )
    assert not invalid.is_valid()
    assert "business_date" in invalid.errors
    assert "recorded_at" in invalid.errors


def test_datetime_widget_has_same_date_mask() -> None:
    form = SampleDateForm()
    assert isinstance(form.fields["recorded_at"].widget, JalaliDateTimeInput)
    assert form.fields["recorded_at"].widget.attrs["data-input-mask"] == "####/##/##"
