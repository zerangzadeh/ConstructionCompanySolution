from __future__ import annotations

from datetime import date
from pathlib import Path

from django import forms
from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

from core.forms import JalaliDateMixin


class JalaliEventForm(JalaliDateMixin, forms.Form):
    event_on = forms.DateField(
        label="تاریخ رویداد", help_text="با تقویم جلالی وارد کنید."
    )


class AccessibleFieldForm(forms.Form):
    description = forms.CharField(
        label="توضیحات",
        help_text="شرح کوتاه وارد کنید.",
        widget=forms.TextInput(attrs={"aria-describedby": "external-description"}),
    )


class Cep003LocalizationAccessibilityTests(SimpleTestCase):
    def test_persian_jalali_date_input_preserves_gregorian_storage_semantics(
        self,
    ) -> None:
        form = JalaliEventForm(data={"event_on": "۱۴۰۵/۰۶/۲۳"})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["event_on"], date(2026, 9, 14))
        self.assertIn('data-jalali-date="date"', str(form["event_on"]))

    def test_shared_field_component_associates_help_and_errors_without_dropping_existing_ids(
        self,
    ) -> None:
        form = AccessibleFieldForm(data={"description": ""})
        self.assertFalse(form.is_valid())

        rendered = Template(
            '{% include "components/form_field.html" with field=form.description only %}'
        ).render(Context({"form": form}))

        self.assertIn('id="id_description-help"', rendered)
        self.assertIn('id="id_description-errors"', rendered)
        self.assertIn(
            'aria-describedby="external-description id_description-help id_description-errors"',
            rendered,
        )
        self.assertIn('aria-invalid="true"', rendered)

    def test_login_landmarks_and_product_shell_are_persian_first(self) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        login = (template_root / "accounts" / "login.html").read_text(encoding="utf-8")
        base = (template_root / "base.html").read_text(encoding="utf-8")

        self.assertIn('<div class="bonira-login__layout">', login)
        self.assertNotIn("<main", login)
        self.assertIn('<main id="main-content"', base)
        self.assertIn('<h1 id="login-title">', login)
        self.assertIn('<html lang="fa" dir="rtl">', base)
        self.assertIn("{% block title %}بنیرا{% endblock %}", base)

    def test_user_visible_templates_do_not_retain_the_legacy_product_name(self) -> None:
        root = Path(settings.BASE_DIR)
        template_sources = [
            *root.glob("templates/**/*.html"),
            *root.glob("apps/**/templates/**/*.html"),
        ]
        template_sources.append(root / "config" / "urls.py")

        legacy_names = ("سازه‌یار", "سازه یار")
        remaining = [
            str(path.relative_to(root))
            for path in template_sources
            if any(name in path.read_text(encoding="utf-8") for name in legacy_names)
        ]

        self.assertEqual(remaining, [])
