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


class DeferredUiPatternTests(SimpleTestCase):
    def test_all_safety_quality_states_have_explicit_semantics_and_domain_labels(self):
        from apps.accounts.templatetags.erp_format import status_family
        from apps.quality.models import QualityIssueStatus
        from apps.safety.models import SafetyIncidentStatus

        badge = Template(
            '{% include "components/status_badge.html" with status=status label=label only %}'
        )
        for choices in (SafetyIncidentStatus, QualityIssueStatus):
            for state, label in choices.choices:
                with self.subTest(state=state):
                    self.assertNotEqual(status_family(state), "neutral")
                    rendered = badge.render(Context({"status": state, "label": label}))
                    self.assertIn(label, rendered)
        self.assertEqual(status_family("unregistered_state"), "neutral")
        self.assertEqual(status_family("draft"), "neutral")
        self.assertEqual(status_family("resolved"), "success")
        self.assertEqual(status_family("awaiting_verification"), "warning")

    def test_badges_localize_on_server_and_escape_untrusted_labels(self):
        badge = Template(
            '{% include "components/status_badge.html" with status=status label=label only %}'
        )
        self.assertIn(
            "پیش‌نویس", badge.render(Context({"status": "draft", "label": "Draft"}))
        )
        self.assertIn(
            "&lt;script&gt;",
            badge.render(Context({"status": "draft", "label": "<script>"})),
        )
        base = (Path(settings.BASE_DIR) / "templates/base.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("createTreeWalker", base)

    def test_navigation_denies_ungranted_destinations_and_has_no_dead_placeholders(
        self,
    ):
        nav = Template('{% include "components/navigation_links.html" %}')
        denied = nav.render(
            Context(
                {"navigation_is_authenticated": True, "business_permission_codes": []}
            )
        )
        allowed = nav.render(
            Context(
                {
                    "navigation_is_authenticated": True,
                    "business_permission_codes": ["tender_bids.view"],
                }
            )
        )
        self.assertNotIn('href="/commercial/"', denied)
        self.assertEqual(allowed.count('href="/commercial/"'), 1)
        self.assertNotIn("is-unavailable", allowed)
        self.assertNotIn("کنترل پروژه", allowed)

    def test_ess_grouping_preserves_permission_gates(self):
        nav = Template('{% include "workforce/_ess_navigation.html" %}')
        denied = nav.render(Context({"business_permission_codes": []}))
        allowed = nav.render(
            Context(
                {
                    "business_permission_codes": [
                        "payroll_ess.view_own",
                        "ess_evidence.view_own",
                    ]
                }
            )
        )
        for title in ("درخواست‌ها و حضور", "حقوق و مزایا", "اطلاعات شغلی و اسناد"):
            self.assertIn(title, allowed)
        self.assertNotIn("سوابق حقوق من", denied)
        self.assertIn("سوابق حقوق من", allowed)
        self.assertIn("سوابق و اسناد من", allowed)


class DeferredUiReferenceTests(SimpleTestCase):
    def test_linked_journal_requires_accounting_permission_and_matching_tenant(self):
        from unittest.mock import patch

        from apps.treasury.views import _linked_journal

        request = SimpleNamespace(user=object(), organization=object())
        movement = SimpleNamespace(journal_id="journal-1")
        with (
            patch("apps.treasury.views.has_business_permission", return_value=False),
            patch("apps.treasury.views.JournalEntry.objects.filter") as query,
        ):
            self.assertIsNone(_linked_journal(request, movement))
            query.assert_not_called()
        with (
            patch("apps.treasury.views.has_business_permission", return_value=True),
            patch("apps.treasury.views.JournalEntry.objects.filter") as query,
        ):
            _linked_journal(request, movement)
            query.assert_called_once_with(
                pk="journal-1", organization=request.organization
            )
            query.return_value.only.assert_called_once_with("pk", "number")

    def test_knowledge_document_enrichment_uses_dms_guard_and_fails_closed(self):
        from unittest.mock import Mock, patch

        from django.core.exceptions import PermissionDenied

        from apps.knowledge.views import _history_source_rows

        request = SimpleNamespace(
            user=object(), organization=SimpleNamespace(pk="tenant-a")
        )
        foreign = SimpleNamespace(
            source_organization_id="tenant-b", document_id="foreign"
        )
        allowed = SimpleNamespace(
            source_organization_id="tenant-a",
            source_type="field_observation",
            source_id="source-1",
            source_version="1",
            document_id="document-1",
            document_version=SimpleNamespace(
                document_id="document-1", organization_id="tenant-a", version_number=2
            ),
        )
        item = SimpleNamespace(candidate_revision=SimpleNamespace(source_pins=Mock()))
        item.candidate_revision.source_pins.all.return_value = [foreign, allowed]
        with (
            patch(
                "apps.knowledge.views.visible_references",
                return_value=(
                    [("source", [("field_observation:source-1:1", "عنوان منبع")])],
                    {},
                ),
            ),
            patch(
                "apps.knowledge.views.get_organization_document",
                side_effect=PermissionDenied,
            ) as get_document,
        ):
            rows = _history_source_rows(request, item)
            get_document.assert_called_once_with(
                user=request.user,
                organization=request.organization,
                document_id="document-1",
            )
            self.assertTrue(all(not row["document_reference"] for row in rows))
        document = SimpleNamespace(
            pk="document-1", title="مدرک مبنا", document_number="DOC-1"
        )
        with (
            patch(
                "apps.knowledge.views.visible_references",
                return_value=(
                    [("source", [("field_observation:source-1:1", "عنوان منبع")])],
                    {},
                ),
            ),
            patch(
                "apps.knowledge.views.get_organization_document", return_value=document
            ),
        ):
            rows = _history_source_rows(request, item)
            self.assertIn("DOC-1", rows[1]["document_reference"])
            self.assertIn("نسخه 2", rows[1]["document_reference"])
            allowed.document_version.organization_id = "tenant-b"
            self.assertFalse(
                _history_source_rows(request, item)[1]["document_reference"]
            )

    def test_sealed_upload_retry_key_is_hidden_and_survives_invalid_redisplay(self):
        from apps.procurement.forms import SealedEvidenceUploadForm

        form = SealedEvidenceUploadForm()
        key = form["idempotency_key"].value()
        self.assertTrue(form["idempotency_key"].is_hidden)
        self.assertEqual(len(key), 32)
        self.assertEqual(form["idempotency_key"].value(), key)
        bound = SealedEvidenceUploadForm(data={"idempotency_key": key})
        self.assertFalse(bound.is_valid())
        self.assertEqual(bound["idempotency_key"].value(), key)
        self.assertFalse(form.fields["expected_sha256"].required)

    def test_audit_reference_uses_retained_allowlist_and_never_live_object_lookup(self):
        from apps.accounts.templatetags.erp_format import (
            audit_business_reference,
            audit_entity_label,
        )

        event = SimpleNamespace(
            entity_type="projects.Project",
            metadata={"code": "PRJ-01", "token": "secret"},
        )
        self.assertEqual(audit_business_reference(event), "PRJ-01")
        event.entity_type = "workforce.Person"
        self.assertNotEqual(audit_business_reference(event), "PRJ-01")
        self.assertNotIn("secret", audit_business_reference(event))
        self.assertNotIn("workforce", audit_entity_label(event.entity_type))
        self.assertEqual(audit_entity_label("unregistered.Model"), "رکورد ثبت‌شده")

    def test_financial_disclosure_labels_preserve_unknown_issue_traceability(self):
        from apps.accounts.templatetags.erp_format import (
            reconciliation_issue_fa,
            source_authority_fa,
        )

        for kind in ("manual", "opening", "correction"):
            for suffix in (
                "count_mismatch",
                "amount_mismatch",
                "source_version_mismatch",
                "exact_line_mismatch",
                "dimension_mismatch",
                "correction_chain_mismatch",
            ):
                self.assertIn("مغایرت", reconciliation_issue_fa(f"{kind}_{suffix}"))
        self.assertIn("جزئیات", reconciliation_issue_fa("unregistered"))
        self.assertEqual(source_authority_fa("Accounting / GL"), "دفتر کل حسابداری")

    def test_custody_records_share_named_primary_and_explicit_detail_links(self):
        from uuid import uuid4

        from django.template.loader import render_to_string

        count = SimpleNamespace(
            pk=uuid4(),
            count_number="COUNT-1",
            warehouse=SimpleNamespace(name="انبار"),
            get_status_display="پیش‌نویس",
        )
        transfer = SimpleNamespace(
            pk=uuid4(), transfer_number="TRANSFER-1", get_status_display="در راه"
        )
        rendered = render_to_string(
            "inventory/custody_workbench.html",
            {"counts": [count], "transfers": [transfer]},
        )
        self.assertIn('aria-label="مشاهده جزئیات COUNT-1"', rendered)
        self.assertIn('aria-label="مشاهده جزئیات TRANSFER-1"', rendered)

    def test_treasury_disclosures_retain_hash_without_primary_exposure(self):
        from html.parser import HTMLParser
        from uuid import uuid4

        from django.template.loader import render_to_string

        class TraceParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = 0
                self.locations = []

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.depth += 1

            def handle_endtag(self, tag):
                if tag == "details":
                    self.depth -= 1

            def handle_data(self, text):
                if "f" * 64 in text:
                    self.locations.append(self.depth)

        run = SimpleNamespace(
            pk=uuid4(),
            cutoff_date=date(2026, 10, 25),
            exceptions=[{}],
            evidence_hash="f" * 64,
            review=None,
            issued_total=10,
            settled_total=3,
            outstanding_total=7,
        )
        for name, context in (
            ("treasury/workbench.html", {"gl_runs": [run]}),
            ("treasury/operations.html", {"advance_runs": [run]}),
        ):
            with self.subTest(template=name):
                parser = TraceParser()
                parser.locations = []
                parser.feed(render_to_string(name, context))
                self.assertTrue(parser.locations)
                self.assertTrue(all(depth > 0 for depth in parser.locations))

    def test_statutory_correction_and_schema_disclosures_render_populated_rows(self):
        from decimal import Decimal
        from uuid import uuid4

        from django.template.loader import render_to_string

        calculation = SimpleNamespace(
            pk=uuid4(),
            run=SimpleNamespace(code="RUN-1"),
            get_kind_display="مالیات حقوق",
            get_record_kind_display="اصلاح",
            revision=2,
            corrects_id=uuid4(),
            policy_version=SimpleNamespace(version=1),
            total_basis=Decimal(100),
            employee_amount=Decimal(10),
            employer_amount=Decimal(0),
            other_amount=Decimal(0),
            review=None,
        )
        rendered = render_to_string(
            "payroll/statutory_workbench.html", {"calculations": [calculation]}
        )
        self.assertIn("ردیابی محاسبه قبلی", rendered)
        self.assertIn(str(calculation.corrects_id), rendered)
        self.assertIn("نسخه مقررات محاسبه", rendered)
        self.assertIn("در انتظار بررسی", rendered)

    def test_navigation_uses_existing_availability_flags_and_omits_empty_groups(self):
        nav = Template('{% include "components/navigation_links.html" %}')
        denied = nav.render(
            Context(
                {"navigation_is_authenticated": True, "business_permission_codes": []}
            )
        )
        self.assertNotIn("erp-nav-group", denied)
        available = nav.render(
            Context(
                {
                    "navigation_is_authenticated": True,
                    "business_permission_codes": [],
                    "my_requests_workspace_available": True,
                    "manager_workspace_available": True,
                }
            )
        )
        self.assertIn('href="/workflows/my-requests/"', available)
        self.assertIn('href="/workflows/manager/"', available)
