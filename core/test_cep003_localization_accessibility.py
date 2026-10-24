from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.forms.models import ModelChoiceIteratorValue
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

from apps.projects.models import Project, ProjectSite
from core.forms import JalaliDateMixin, attach_parent_choice_ui


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

    def test_specific_field_labels_override_only_generated_name_fallbacks(self) -> None:
        class JournalForm(forms.Form):
            description = forms.CharField(label="شرح سند")
            code = forms.CharField(label="کد حساب")
            name = forms.CharField()

        form = JournalForm()
        template = Template(
            '{% include "components/form_field.html" with field=field only %}'
        )
        for field, label in (
            ("description", "شرح سند"),
            ("code", "کد حساب"),
            ("name", "نام"),
        ):
            with self.subTest(field=field):
                rendered = template.render(Context({"field": form[field]}))
                self.assertIn(label, rendered)

    def test_bounded_pagination_preserves_filters_sort_and_repeated_values(
        self,
    ) -> None:
        request = RequestFactory().get(
            "/records/?status=approved&sort=code&tag=a&tag=b&page=2"
        )
        rendered = Template(
            '{% include "components/bounded_table_pagination.html" %}'
        ).render(
            Context({"request": request, "page_obj": Paginator(range(6), 2).page(2)})
        )
        for page in (1, 3):
            self.assertIn(
                f"?status=approved&amp;sort=code&amp;tag=a&amp;tag=b&amp;page={page}",
                rendered,
            )

    def test_parent_choice_binding_adds_metadata_without_expanding_validation(
        self,
    ) -> None:
        class ScopedForm(forms.Form):
            project = forms.ModelChoiceField(queryset=Project.objects.none())
            site = forms.ModelChoiceField(queryset=ProjectSite.objects.none())

        form = ScopedForm(data={"project": "foreign-project", "site": "foreign-site"})
        original_query = form.fields["site"].queryset.query
        attach_parent_choice_ui(form, "site", "project", "project_id")
        widget = form.fields["site"].widget
        self.assertIs(form.fields["site"].queryset.query, original_query)
        self.assertEqual(widget.attrs["data-local-parent"], "id_project")
        option = widget.create_option(
            "site",
            ModelChoiceIteratorValue("site-1", SimpleNamespace(project_id="project-1")),
            "کارگاه یک",
            False,
            1,
        )
        self.assertEqual(option["attrs"]["data-parent-value"], "project-1")
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {"project", "site"})

    def test_related_parent_choices_use_the_same_contract_metadata(self) -> None:
        class EvidenceForm(forms.Form):
            certificate = forms.ModelChoiceField(queryset=Project.objects.none())
            evidence = forms.ModelChoiceField(queryset=ProjectSite.objects.none())

        form = EvidenceForm()
        attach_parent_choice_ui(
            form,
            "evidence",
            "certificate",
            "contract_id",
            parent_value_attribute="contract_id",
        )
        self.assertEqual(
            form.fields["evidence"].widget.attrs["data-local-parent-key"], "parentValue"
        )
        for name in ("certificate", "evidence"):
            option = form.fields[name].widget.create_option(
                name,
                ModelChoiceIteratorValue(
                    name, SimpleNamespace(contract_id="contract-1")
                ),
                name,
                False,
                1,
            )
            self.assertEqual(option["attrs"]["data-parent-value"], "contract-1")

    def test_statutory_submission_generates_hidden_retry_metadata_and_retains_bound_keys(
        self,
    ) -> None:
        from apps.billing.forms import StatutorySubmissionForm

        form = StatutorySubmissionForm()
        data = {name: form[name].value() for name in form.fields}
        self.assertEqual(form.visible_fields(), [])
        self.assertTrue(all(data.values()))
        retry = StatutorySubmissionForm(data=data)
        self.assertTrue(retry.is_valid(), retry.errors)
        self.assertEqual(
            retry.cleaned_data["idempotency_key"], str(data["idempotency_key"])
        )
        self.assertEqual(
            str(retry.cleaned_data["correlation_id"]), str(data["correlation_id"])
        )

    def test_billing_date_forms_preserve_jalali_and_iso_storage_dates(self) -> None:
        from apps.billing import forms as billing_forms
        from apps.organizations.models import Organization

        organization = Organization()
        for name in (
            "GuaranteeForm",
            "GuaranteeRevisionForm",
            "ComplianceEvidenceForm",
            "ComplianceEvidenceRevisionForm",
            "RetentionReleaseForm",
            "PayableMeasurementForm",
            "PayableCertificateForm",
        ):
            form_class = getattr(billing_forms, name)
            form = form_class(organization=organization)
            date_fields = [
                key
                for key, field in form.fields.items()
                if isinstance(field, forms.DateField)
            ]
            self.assertTrue(date_fields, name)
            for raw in ("۱۴۰۵/۰۶/۲۳", "2026-09-14"):
                bound = form_class(
                    data={key: raw for key in date_fields}, organization=organization
                )
                for key in date_fields:
                    with self.subTest(form=name, field=key, raw=raw):
                        self.assertIn('data-jalali-date="date"', str(form[key]))
                        self.assertEqual(
                            bound.fields[key].clean(bound.data[key]), date(2026, 9, 14)
                        )

    def test_journal_dimensions_use_draft_relations_and_frozen_submitted_labels(
        self,
    ) -> None:
        from decimal import Decimal
        from uuid import uuid4

        from django.template.loader import render_to_string

        journal = SimpleNamespace(pk=uuid4(), status="draft", description="Journal")
        line = SimpleNamespace(
            line_number=1,
            account="Cash",
            debit=Decimal(1),
            credit=Decimal(0),
            project=SimpleNamespace(code="P1", name="Draft project"),
            site=None,
            wbs_node=None,
            party=None,
            dimension_snapshot={
                "project": {"id": str(uuid4()), "code": "P0", "name": "Frozen project"}
            },
            source_line_uuid=uuid4(),
        )
        context = {"journal": journal, "lines": [line], "business_permission_codes": []}
        rendered = render_to_string("accounting/journal_detail.html", context)
        self.assertIn("Draft project", rendered)
        self.assertNotIn("Frozen project", rendered)
        journal.status = "posted"
        rendered = render_to_string("accounting/journal_detail.html", context)
        self.assertIn("Frozen project", rendered)
        self.assertNotIn("Draft project", rendered)

    def test_working_weekday_choices_preserve_integer_values_and_legacy_input(
        self,
    ) -> None:
        from apps.timekeeping.forms import CalendarForm

        for weekdays in (["6", "1"], "6,1"):
            form = CalendarForm(
                data={
                    "code": "CAL",
                    "name": "تقویم",
                    "effective_from": "2026-09-14",
                    "working_weekdays": weekdays,
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["working_weekdays"], [6, 1])
            self.assertIn("شنبه", str(form["working_weekdays"]))
        for value in (["0"], ["8"], ["invalid"], []):
            with self.subTest(value=value), self.assertRaises(forms.ValidationError):
                CalendarForm().fields["working_weekdays"].clean(value)

    def test_manual_journal_retry_key_and_required_opening_references_are_preserved(
        self,
    ) -> None:
        from apps.accounting.forms import JournalForm, OpeningImportForm
        from apps.organizations.models import Organization

        organization = Organization()
        form = JournalForm(organization=organization)
        key = str(form["source_key"].value())
        self.assertTrue(form.fields["source_key"].widget.is_hidden)
        self.assertTrue(key)
        retry = JournalForm(data={"source_key": key}, organization=organization)
        self.assertEqual(
            retry.fields["source_key"].clean(retry["source_key"].value()), key
        )
        for name in ("evidence_reference", "reconciliation_reference"):
            self.assertFalse(form.fields[name].required)
            self.assertTrue(
                OpeningImportForm(organization=organization).fields[name].required
            )

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
