"""Work-record presentation, exact quantities and existing access boundaries."""

from decimal import Decimal

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.templatetags.erp_format import erp_quantity_fa
from apps.billing.models import ProgressRecord
from apps.billing.services import (
    create_progress_correction,
    reject_progress_record,
    request_progress_verification,
)
from apps.billing.test_mvp03 import JourneyFixture


class WorkQuantityTests(SimpleTestCase):
    def test_exact_localized_quantities(self):
        for value, expected in (
            ("0.0000", "۰"),
            ("-12.0345", "-۱۲٫۰۳۴۵"),
            ("99999999999999.9999", "۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٫۹۹۹۹"),
            ("0.0001", "۰٫۰۰۰۱"),
            ("140400.0225", "۱۴۰٬۴۰۰٫۰۲۲۵"),
        ):
            with self.subTest(value=value):
                self.assertEqual(erp_quantity_fa(Decimal(value)), expected)
        self.assertIsNone(erp_quantity_fa(None))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkRecordDetailTests(JourneyFixture, TestCase):
    def setUp(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        synchronize_authorization_catalog(using="default")
        self.make_fixture(persian=True)
        self.login(self.owner)

    def detail(self, record):
        return self.client.get(reverse("billing:progress_detail", args=[record.pk]))

    def test_verified_evidence_and_navigation_are_preserved(self):
        record = self._verified_record()
        before = ProgressRecord.objects.values().get(pk=record.pk)
        response = self.detail(record)
        for text in (
            "جزئیات کارکرد",
            "کارکرد این ثبت",
            "کارکرد تجمعی تا این ثبت",
            "مقدار مبنای قلم",
            "بررسی‌کننده",
            "زمان بررسی",
            record.verification_reason,
            record.source_reference,
            record.evidence,
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "اندازه‌گیری")
        self.assertContains(response, "measurement-value-primary")
        self.assertIn("line_key=ITEM-01", response.context["history_url"])
        self.assertIn(f"contract={self.contract.pk}", response.context["history_url"])
        self.assertEqual(
            response.context["page_breadcrumbs"][-2]["url"],
            response.context["history_url"],
        )
        self.assertEqual(before, ProgressRecord.objects.values().get(pk=record.pk))
        self.assertEqual(
            self.client.get(response.context["history_url"]).status_code, 200
        )

    def test_draft_pending_rejected_and_optional_fields(self):
        record = self._record()
        response = self.detail(record)
        self.assertContains(response, "هنوز برای راستی‌آزمایی ارسال نشده")
        self.assertNotContains(response, "<dt>بررسی‌کننده</dt>")
        self.assertNotContains(response, "<dt>زمان بررسی</dt>")
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        self.login(self.manager)
        response = self.detail(record)
        self.assertContains(response, "در انتظار بررسی")
        self.assertContains(
            response, reverse("billing:progress_verify", args=[record.pk])
        )
        reject_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="اصلاح مدرک DR-001 لازم است",
        )
        response = self.detail(record)
        self.assertContains(response, "اصلاح مدرک DR-001 لازم است")
        self.assertContains(response, "<dt>زمان بررسی</dt>", html=True)
        self.assertNotContains(response, "progress-verify-reason")

    def test_correction_preserves_original_baseline_and_history(self):
        original = self._verified_record()
        correction = create_progress_correction(
            organization=self.organization,
            actor=self.owner,
            record=original,
            source_type="correction_sheet",
            source_reference="COR-DETAIL-001",
            period_quantity=Decimal("0.4001"),
            cumulative_quantity=Decimal("0.4001"),
            evidence="مدرک اصلاحی\nCOR-DETAIL-001",
        )
        response = self.detail(correction)
        self.assertContains(response, "ثبت اصلاحی")
        self.assertContains(response, "۰٫۴۰۰۱")
        self.assertEqual(
            response.context["progress_record"].baseline_id, original.baseline_id
        )
        self.assertEqual(response.context["progress_record"].corrects_id, original.pk)
        self.assertIn("line_key=ITEM-01", response.context["history_url"])
        original.refresh_from_db()
        self.assertEqual(original.cumulative_quantity, Decimal("0.5000"))

    def test_historical_unmapped_and_extreme_values_render_without_reconstruction(self):
        record = self._verified_record()
        replacement = self._approved_baseline()
        response = self.detail(record)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(
            response.context["progress_record"].baseline_id, replacement.pk
        )
        self.assertContains(response, "جایگزین‌شده")
        self.assertEqual(response.context["progress_record"].baseline.version, 1)
        # Presentation-only historical/missing-data fixtures; never write finalized data.
        record.baseline.version = 1
        record.baseline_item.activity = None
        record.baseline_item.wbs_node = None
        record.period_quantity = Decimal("-99999999999999.9999")
        record.cumulative_quantity = Decimal("0.0001")
        record.source_reference = ""
        record.evidence = "<script>audit</script>\nBONIRA-WORK-REVIEW-001"
        record.verified_by = None
        record.verified_at = None
        html = render_to_string(
            "billing/progress_detail.html",
            {
                "progress_record": record,
                "history_url": "/billing/progress/?line_key=ITEM-01",
            },
        )
        self.assertIn("-۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٫۹۹۹۹", html)
        self.assertIn("۰٫۰۰۰۱", html)
        self.assertIn("مرجعی ثبت نشده است.", html)
        self.assertIn("&lt;script&gt;audit&lt;/script&gt;", html)
        self.assertIn("BONIRA-WORK-REVIEW-001", html)
        self.assertNotIn("<dt>بررسی‌کننده</dt>", html)
        self.assertNotIn("<dt>زمان بررسی</dt>", html)

    def test_read_only_scoped_reader_has_no_decision_or_contract_link(self):
        from apps.projects.test_command_center import scoped_reader

        record = self._record()
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["progress.view"],
            username="work-detail-reader",
        )
        self.login(reader)
        response = self.detail(record)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "progress-verify-reason")
        self.assertNotContains(
            response, reverse("contracts:detail", args=[self.contract.pk])
        )
        self.assertNotContains(
            response, reverse("billing:progress_verify", args=[record.pk])
        )
        from apps.organizations.models import Organization
        from apps.organizations.services import set_active_organization

        other = Organization.objects.create(
            name="Other work detail tenant", slug="work-detail-other"
        )
        session = self.client.session
        set_active_organization(session, other)
        session.save()
        self.assertIn(self.detail(record).status_code, (302, 403, 404))
