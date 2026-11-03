"""Print is another scoped representation, with frozen history and no writes."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.services import submit_progress_claim
from apps.billing.test_mvp03 import JourneyFixture
from apps.daily_reports.models import DailyReport
from apps.expenses.models import Expense, PlatformExpenseGroup
from apps.expenses.services import create_expense
from apps.organizations.models import MembershipScopeGrant, OrganizationStatus
from apps.procurement import services as purchasing
from apps.procurement.models import GoodsReceipt, PurchaseOrder
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.projects.models import Project, ProjectSite
from core.jalali import format_jalali


class PrintAssertions:
    def output(self, route, params=None):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(route, {**(params or {}), "format": "print"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertContains(response, '<html lang="fa" dir="rtl">')
        self.assertNotContains(response, "data-module-selector")
        self.assertNotContains(response, 'id="sidebar"')
        self.assertNotContains(response, "csrfmiddlewaretoken")
        self.assertNotRegex(response.content.decode(), r">\s*[a-f0-9]{8}-[a-f0-9]{4}-")
        writes = [
            q["sql"]
            for q in queries
            if q["sql"].split()[0].upper() in ("UPDATE", "INSERT", "DELETE")
            and "django_session" not in q["sql"]
        ]
        self.assertEqual(writes, [])
        return response


class PrintFoundationTests(SimpleTestCase):
    def test_timezone_uses_organization_and_preserves_decimal_precision(self):
        from types import SimpleNamespace

        from core.printing import moment, value

        organization = SimpleNamespace(settings=SimpleNamespace(timezone="Asia/Tehran"))
        self.assertTrue(
            moment(
                datetime(2026, 11, 3, 21, 0, tzinfo=UTC), organization
            ).text.endswith("00:30")
        )
        self.assertEqual(
            value(Decimal("123456789012.1234")).text, "123,456,789,012.1234"
        )
        self.assertEqual(value(Decimal(0)).text, "0")

    def test_logo_is_bounded_validated_raster_and_never_a_remote_url(self):
        from base64 import b64decode
        from types import SimpleNamespace

        from django.core.files.base import ContentFile

        from core.printing import _logo

        logo = ContentFile(
            b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII="
            ),
            name="logo.png",
        )
        organization = SimpleNamespace(settings=SimpleNamespace(logo=logo))
        self.assertTrue(_logo(organization).startswith("data:image/png;base64,"))
        organization.settings.logo = ContentFile(
            b'<svg onload="alert(1)"></svg>', name="logo.svg"
        )
        self.assertEqual(_logo(organization), "")
        organization.settings.logo = ContentFile(b"not a raster", name="logo.png")
        self.assertEqual(_logo(organization), "")


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class BillingPrintTests(PrintAssertions, JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)

    def test_draft_persisted_quantities_and_totals_without_calculation(self):
        claim = self._claim()
        with patch(
            "apps.billing.services.recalculate_progress_claim",
            side_effect=AssertionError("read only"),
        ):
            response = self.output(reverse("billing:claim_detail", args=[claim.pk]))
        document = response.context["document"]
        self.assertEqual(str(document.reference), str(claim.claim_number))
        self.assertEqual(document.tables[0].rows[0][-1].text, "60")
        self.assertContains(response, claim.contract.title)
        self.assertContains(response, "ناخالص")
        self.assertEqual(len(document.totals), 3)
        self.assertEqual(document.totals[-1][1].text, "60")
        self.assertNotContains(response, "contract_term.retention")
        self.assertNotContains(response, str(claim.pk) + "</")

    def test_submitted_revision_print_uses_snapshot_even_after_in_memory_changes(self):
        from apps.billing.print_outputs import claim_document

        claim = self._claim()
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        claim.refresh_from_db()
        saved = claim.submission_snapshot
        claim.net_amount = Decimal(9999)
        claim.items.get()  # Do not mutate the immutable database history.
        document = claim_document(claim)
        self.assertEqual(document.totals[-1][1].text, "60")
        self.assertEqual(document.tables[0].rows[0][-1].text, "60")
        self.assertEqual(saved, claim.submission_snapshot)
        response = self.output(reverse("billing:claim_detail", args=[claim.pk]))
        self.assertContains(response, "ارسال‌شده برای تأیید")

    def test_missing_permission_foreign_tenant_project_scope_and_anonymous(self):
        from apps.organizations.services import (
            create_organization_with_owner,
            set_active_organization,
        )

        claim = self._claim()
        route = reverse("billing:claim_detail", args=[claim.pk])
        actor = User.objects.create_user(username="no-claim-print")
        self.organization.memberships.create(user=actor, role="viewer", status="active")
        self.login(actor)
        self.assertEqual(self.client.get(route, {"format": "print"}).status_code, 403)
        foreign = create_organization_with_owner(
            owner=actor, name="Foreign", slug="foreign-print"
        )
        session = self.client.session
        set_active_organization(session, foreign)
        session.save()
        self.assertEqual(self.client.get(route, {"format": "print"}).status_code, 404)
        self.login(self.owner)
        MembershipScopeGrant.objects.filter(membership__user=self.owner).delete()
        self.assertIn(
            self.client.get(route, {"format": "print"}).status_code, (403, 404)
        )
        self.client.logout()
        self.assertEqual(self.client.get(route, {"format": "print"}).status_code, 302)


class OperationalPrintFixture(ReceiptJourneyFixture):
    def sources(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.assertEqual(self.add(receipt, item, "3").status_code, 302)
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="PRINT",
            name="کارگاه شمال",
        )
        report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 11, 3),
            work_performed="بتن‌ریزی پی",
            weather_conditions="آفتابی",
            created_by=self.owner,
        )
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "سایر هزینه‌ها"}
        )
        expense = create_expense(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            description="هزینه حمل مصالح",
            amount=Decimal("12345.67"),
            incurred_on=date(2026, 11, 3),
            receipt_reference="REC-007",
        )
        return order, receipt, report, expense

    def routes(self, sources):
        order, receipt, report, _ = sources
        return [
            reverse("procurement:order_detail", args=[order.pk]),
            reverse("procurement:receipt_detail", args=[receipt.pk]),
            reverse("daily_reports:detail", args=[report.pk]),
            reverse("expenses:list"),
        ]


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalPrintTests(PrintAssertions, OperationalPrintFixture, TestCase):
    def test_all_four_source_documents_have_identity_values_and_no_mutations(self):
        sources = self.sources()
        order, receipt, report, expense = sources
        before = self.financial_snapshot()
        for route, expected in zip(
            self.routes(sources),
            (
                order.order_number,
                receipt.receipt_number,
                report.work_performed,
                expense.description,
            ),
        ):
            with self.subTest(route=route):
                response = self.output(route)
                self.assertContains(response, expected)
        self.assertEqual(self.financial_snapshot(), before)
        self.assertEqual(PurchaseOrder.objects.get(pk=order.pk).status, "issued")
        self.assertEqual(GoodsReceipt.objects.get(pk=receipt.pk).status, "draft")
        self.assertEqual(Expense.objects.get(pk=expense.pk).amount, Decimal("12345.67"))

    def test_permissions_and_cross_tenant_all_four_routes(self):
        sources = self.sources()
        actor = User.objects.create_user(username="no-operational-print")
        self.organization.memberships.create(user=actor, role="viewer", status="active")
        self.login(actor)
        for route in self.routes(sources):
            self.assertEqual(
                self.client.get(route, {"format": "print"}).status_code, 403
            )
        self.login(self.outsider)
        for route in self.routes(sources)[:3]:
            self.assertIn(
                self.client.get(route, {"format": "print"}).status_code, (403, 404)
            )
        response = self.output(reverse("expenses:list"))
        self.assertNotContains(response, sources[-1].description)
        self.assertContains(response, "موردی ثبت نشده است")

    def test_project_scope_and_cancelled_tenant_all_four_routes(self):
        sources = self.sources()
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        other = Project.objects.create(
            organization=self.organization, code="PRINT-OUT", name="خارج از دامنه"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="print boundary",
        )
        for route in self.routes(sources)[:3]:
            self.assertIn(
                self.client.get(route, {"format": "print"}).status_code, (403, 404)
            )
        self.assertNotContains(
            self.output(reverse("expenses:list")), sources[-1].description
        )
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])
        for route in self.routes(sources):
            self.assertIn(
                self.client.get(route, {"format": "print"}).status_code, (302, 403)
            )

    def test_expense_filters_full_dataset_empty_optional_and_no_cash_balances(self):
        sources = self.sources()
        route = reverse("expenses:list")
        response = self.output(
            route,
            {
                "incurred_on_from": "2026-11-03",
                "project": self.project.name,
                "page_size": "1",
                "page": "4",
            },
        )
        self.assertContains(response, "REC-007")
        self.assertContains(response, format_jalali(date(2026, 11, 3)))
        self.assertContains(response, "12,345.67")
        self.assertNotContains(response, "مانده")
        self.assertNotContains(response, "Treasury")
        self.assertContains(
            self.output(route, {"description": "missing"}), "موردی ثبت نشده است"
        )
        self.assertNotContains(
            self.output(route, {"incurred_on_to": "2020-01-01"}),
            sources[-1].description,
        )

    def test_escape_long_content_csp_and_local_assets(self):
        order, _, _, _ = self.sources()
        from django.test import RequestFactory

        from apps.procurement.print_outputs import order_document
        from core.printing import print_response

        order.notes = (
            '<img src="https://evil.invalid/x" onerror="alert(1)"><script>x</script>'
            + "متن بلند " * 500
        )
        request = RequestFactory().get(
            reverse("procurement:order_detail", args=[order.pk]), {"format": "print"}
        )
        request.organization = self.organization
        request.user = self.owner
        response = print_response(request, order_document(order))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<img src="https://')
        self.assertNotContains(response, "<script>x</script>")
        self.assertContains(response, "css/erp_print.css")

    def test_po_and_grn_pinned_version_descriptions_not_mutable_base_item(self):
        from apps.procurement.print_outputs import order_document, receipt_document

        order, receipt, _, _ = self.sources()
        line = order.current_version.lines.get()
        # Mock only the base-line description; domain history is never edited.
        with patch.object(
            type(line.source_item), "description", "MUTABLE", create=True
        ):
            document = order_document(order)
            grn = receipt_document(receipt)
        self.assertIn(line.description, document.tables[0].rows[0][0].text)
        self.assertIn(line.description, grn.tables[0].rows[0][0].text)
        self.assertNotIn("MUTABLE", document.tables[0].rows[0][0].text)
        self.assertEqual(dict(grn.metadata)["نسخه سفارش مبنا"].text, "1")

    def test_constant_queries_for_long_order_and_empty_draft(self):
        from apps.procurement.print_outputs import order_document

        draft, _ = self.make_order(number="LONG-PO", issued=False)
        self.login(self.owner)
        route = reverse("procurement:order_detail", args=[draft.pk])
        with CaptureQueriesContext(connection) as first:
            self.output(route)
        for i in range(40):
            purchasing.add_purchase_order_item(
                organization=self.organization,
                actor=self.owner,
                purchase_order=draft,
                material=self.material,
                description=f"ردیف بلند {i}",
                quantity=Decimal(1),
                unit_price=Decimal("13.25"),
            )
        with CaptureQueriesContext(connection) as many:
            response = self.output(route)
        self.assertLessEqual(len(many), len(first) + 1)
        self.assertEqual(len(response.context["document"].tables[0].rows), 41)
        empty = purchasing.create_purchase_order(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            supplier=self.supplier,
            order_number="EMPTY-PO",
            order_date=date(2026, 11, 3),
        )
        self.assertEqual(order_document(empty).tables[0].rows, [])

    def test_changed_po_uses_version_two_and_old_grn_keeps_version_one(self):
        from apps.organizations.models import MembershipRoleAssignment
        from apps.procurement.source_to_pay_services import (
            decide_purchase_order_change,
            request_purchase_order_change,
        )

        order, receipt, _, _ = self.sources()
        original = order.current_version
        member = self.organization.memberships.get(user=self.member)
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=member.role_definition,
            source="test_fixture",
            reason="Independent synthetic change approval",
        )
        change = request_purchase_order_change(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            line_changes={str(original.lines.get().pk): (Decimal(8), Decimal("20.25"))},
            reason="اصلاح مقدار و قیمت",
            evidence="صورت‌جلسه نمونه",
            idempotency_key="print-change",
        )
        decide_purchase_order_change(
            organization=self.organization,
            actor=self.member,
            change_request=change,
            approve=True,
            reason="تأیید مستقل نمونه",
        )
        self.login(self.owner)
        po = self.output(reverse("procurement:order_detail", args=[order.pk])).context[
            "document"
        ]
        grn = self.output(
            reverse("procurement:receipt_detail", args=[receipt.pk])
        ).context["document"]
        self.assertEqual(dict(po.metadata)["نسخه سفارش"].text, "2")
        self.assertEqual(po.tables[0].rows[0][2].text, "8")
        self.assertEqual(po.tables[0].rows[0][3].text, "20.25")
        self.assertEqual(po.tables[0].rows[0][4].text, "162")
        self.assertEqual(po.totals, [])
        self.assertEqual(dict(grn.metadata)["نسخه سفارش مبنا"].text, "1")
        self.assertEqual(original.lines.get().unit_price, Decimal("12.50"))

    def test_daily_report_prints_existing_structured_entries_and_approvals_only(self):
        from apps.daily_reports import services as daily

        _order, _receipt, report, _expense = self.sources()
        args = {
            "organization": self.organization,
            "report_id": str(report.pk),
            "actor": self.owner,
        }
        daily.add_daily_activity(
            **args,
            description="فعالیت بتن‌ریزی",
            quantity=Decimal("2.125"),
            unit_of_measure=self.unit,
            progress_percent=Decimal("25.5"),
        )
        daily.add_daily_report_labor_entry(
            **args,
            team_name="تیم قالب‌بندی",
            worker_count=4,
            hours_worked=Decimal("7.5"),
        )
        daily.add_daily_report_equipment_entry(
            **args, equipment_name="جرثقیل کارگاه", hours_used=Decimal("3.25")
        )
        daily.add_daily_report_material_entry(
            **args,
            material_name="نام ثبت‌شده مصالح",
            quantity=Decimal("1.75"),
            unit="واحد ثبت‌شده",
        )
        daily.add_delay_event(
            **args,
            occurred_on=date(2026, 11, 3),
            cause="تأخیر تحویل",
            impact="توقف اجرا",
            responsible_party="تأمین‌کننده",
            duration_hours=Decimal("1.5"),
        )
        response = self.output(reverse("daily_reports:detail", args=[report.pk]))
        self.assertEqual(len(response.context["document"].tables), 5)
        for text in (
            "فعالیت بتن‌ریزی",
            "2.125",
            "25.5",
            "تیم قالب‌بندی",
            "7.5",
            "جرثقیل کارگاه",
            "3.25",
            "نام ثبت‌شده مصالح",
            "واحد ثبت‌شده",
            "تأخیر تحویل",
            "توقف اجرا",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "اطلاعات تأیید ثبت‌شده")

    def test_version_one_line_amounts_reuse_existing_po_total_precision(self):
        order, _ = self.make_order(number="PRECISION", issued=False)
        item = purchasing.add_purchase_order_item(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            material=self.material,
            quantity=Decimal("1.25"),
            unit_price=Decimal("1000000.25"),
        )
        order = purchasing.issue_purchase_order(
            organization=self.organization, actor=self.owner, purchase_order=order
        )
        self.login(self.owner)
        document = self.output(
            reverse("procurement:order_detail", args=[order.pk])
        ).context["document"]
        self.assertEqual(document.tables[0].rows[-1][-1].text, "1,250,000.31")
        self.assertEqual(item.line_total, Decimal("1250000.31"))
        self.assertEqual(document.totals[0][1].text, "1,250,125.31")
