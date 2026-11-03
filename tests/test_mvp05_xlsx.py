"""Reopen actual downloads and assert source values, scope and cell types."""

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook

from apps.billing.test_mvp03 import JourneyFixture
from apps.expenses.services import create_expense
from apps.inventory.test_mvp04e import InventoryJourneyFixture
from apps.organizations.models import MembershipScopeGrant, OrganizationStatus
from apps.procurement import test_rfq as rfq_fixture
from apps.procurement.test_mvp04f import ConnectedJourneyFixture
from apps.projects.models import Project, ProjectPhase, ProjectSite
from core.xlsx import Column, Sheet, safe_filename, workbook_file


class WorkbookAssertions:
    def workbook(self, route, params=None, *, rows=None):
        response = self.client.get(route, {**(params or {}), "format": "xlsx"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        result = load_workbook(
            BytesIO(b"".join(response.streaming_content)), data_only=False
        )
        for sheet in result:
            self.assertTrue(sheet.sheet_view.rightToLeft)
            self.assertEqual(sheet.freeze_panes, "A2")
            self.assertTrue(sheet.auto_filter.ref)
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type, "f")
                    if isinstance(cell.value, str):
                        self.assertNotRegex(
                            cell.value, r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
                        )
        if rows is not None:
            self.assertEqual(result.active.max_row - 1, rows)
        return result


class FoundationTests(SimpleTestCase):
    def test_types_injection_empty_names_and_long_persian_text(self):
        values = [
            "=1+1",
            "+SUM(A1)",
            "-1+1",
            "@SUM(A1)",
            "\t=1+1",
            "#REF!",
            "0012",
            "متن بلند " * 5000,
        ]
        columns = (
            Column("شرح", "text", 48),
            Column("مقدار", "amount"),
            Column("تاریخ", "day"),
            Column("زمان", "time"),
        )
        from types import SimpleNamespace

        rows = [
            SimpleNamespace(
                text=v,
                amount=Decimal("-123.45"),
                day=date(2026, 11, 3),
                time=datetime(2026, 11, 3, 0, 0, tzinfo=UTC),
            )
            for v in values
        ]
        wb = load_workbook(
            workbook_file(
                (Sheet("'/[]نام؟" * 9, columns, rows), Sheet("خالی", columns, [])),
                timezone_name="Asia/Tehran",
            )
        )
        self.assertLessEqual(len(wb.active.title), 31)
        for index, text in enumerate(values, 2):
            cell = wb.active.cell(index, 1)
            self.assertEqual(cell.data_type, "s")
            self.assertEqual(cell.value, text[:32767])
            self.assertEqual(wb.active.cell(index, 2).data_type, "n")
            self.assertEqual(wb.active.cell(index, 3).data_type, "d")
            self.assertEqual(wb.active.cell(index, 4).value.hour, 3)
        self.assertEqual(wb["خالی"].max_row, 1)
        self.assertEqual([c.value for c in wb["خالی"][1]], [c.label for c in columns])
        self.assertNotRegex(safe_filename("../bad\\file\r\n.xlsx"), r"[/\\\r\n]")


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class BillingExportTests(WorkbookAssertions, JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)

    def test_claim_list_detail_calculation_and_filtered_empty(self):
        from apps.billing.services import recalculate_progress_claim
        from apps.billing.xlsx_exports import (
            ADJUSTMENT_COLUMNS,
            CLAIM_COLUMNS,
            LINE_COLUMNS,
        )

        claim = self._claim()
        claim = recalculate_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        route = reverse("billing:claim_list")
        wb = self.workbook(
            route,
            {"contract": str(claim.contract_id), "project_id": str(claim.project_id)},
            rows=1,
        )
        for sheet, columns in zip(
            wb, [CLAIM_COLUMNS, LINE_COLUMNS, ADJUSTMENT_COLUMNS]
        ):
            self.assertEqual([c.value for c in sheet[1]], [c.label for c in columns])
        self.assertEqual(wb.active["D2"].data_type, "s")
        self.assertEqual(wb.active["G2"].data_type, "d")
        self.assertEqual(Decimal(str(wb.active["M2"].value)), claim.net_amount)
        self.assertEqual(wb["ردیف‌های کارکرد"].max_row - 1, claim.items.count())
        for row, item in zip(
            wb["ردیف‌های کارکرد"].iter_rows(min_row=2),
            claim.items.order_by("baseline_item__sort_order", "pk"),
        ):
            self.assertEqual(Decimal(str(row[9].value)), item.current_amount)
        self.workbook(reverse("billing:claim_detail", args=[claim.pk]), rows=1)
        self.workbook(route, {"status": "approved"}, rows=0)
        self.workbook(route, {"contract": "invalid"}, rows=0)
        other = Project.objects.create(
            organization=self.organization, code="XLSX", name="پروژه دیگر"
        )
        self.workbook(route, {"project_id": str(other.pk)}, rows=0)

    def test_claim_restricted_and_cross_tenant_detail(self):
        from apps.accounts.models import User

        claim = self._claim()
        restricted = User.objects.create_user(username="xlsx-restricted")
        self.organization.memberships.create(
            user=restricted, role="viewer", status="active"
        )
        self.login(restricted)
        self.assertEqual(
            self.client.get(
                reverse("billing:claim_list"), {"format": "xlsx"}
            ).status_code,
            403,
        )
        from apps.organizations.services import (
            create_organization_with_owner,
            set_active_organization,
        )

        foreign = create_organization_with_owner(
            owner=restricted, name="Foreign XLSX", slug="foreign-xlsx"
        )
        self.client.force_login(restricted)
        session = self.client.session
        set_active_organization(session, foreign)
        session.save()
        self.assertEqual(
            self.client.get(
                reverse("billing:claim_detail", args=[claim.pk]), {"format": "xlsx"}
            ).status_code,
            404,
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalExportsTests(WorkbookAssertions, InventoryJourneyFixture, TestCase):
    def test_pr_rfq_po_grn_and_filters(self):
        rfq = rfq_fixture.RequestForQuotationServiceTests._draft(self)
        self.login(self.owner)
        receipt, source = self.received_source()
        routes = [
            "procurement:request_list",
            "procurement:rfq_list",
            "procurement:order_list",
            "procurement:receipt_list",
        ]
        for route in routes:
            with self.subTest(route=route):
                wb = self.workbook(reverse(route), rows=1)
                self.assertEqual(wb["اقلام"].max_row, 2)
                self.workbook(reverse(route), {"q": "missing-export"}, rows=0)
        wb = self.workbook(reverse("procurement:rfq_list"))
        self.assertEqual(wb.active["A2"].value, rfq.rfq_number)
        self.assertEqual(wb.active["D2"].value, rfq.purchase_request.request_number)
        self.assertEqual(wb.active["F2"].data_type, "d")
        wb = self.workbook(reverse("procurement:receipt_list"))
        self.assertEqual(wb.active["A2"].value, receipt.receipt_number)
        self.assertEqual(wb["اقلام"]["E2"].value, float(source.quantity))
        for route in routes:
            self.login(self.outsider)
            self.workbook(reverse(route), rows=0)
        self.login(self.owner)
        self.workbook(
            reverse("procurement:order_list"),
            {"project": str(self.other_project.pk)},
            rows=0,
        )

    def test_inventory_posted_reversal_warehouse_and_project_isolation(self):
        receipt, source = self.received_source()
        record = self.stock_create(source)
        self.assertEqual(self.stock_post(record).status_code, 302)
        self.assertEqual(self.stock_reverse(record).status_code, 302)
        route = reverse("inventory:transaction_list")
        wb = self.workbook(route, rows=2)
        values = list(wb.active.values)
        self.assertEqual({r[11] or r[13] for r in values[1:]}, {receipt.receipt_number})
        self.assertIn(record.transaction_number, [r[12] for r in values[1:]])
        self.assertTrue(all(wb.active.cell(i, 8).data_type == "n" for i in (2, 3)))
        self.workbook(route, {"warehouse": str(self.central.pk)}, rows=0)
        self.workbook(route, {"warehouse": str(self.site.pk)}, rows=2)
        self.workbook(route, {"project": str(self.other_project.pk)}, rows=0)
        self.login(self.outsider)
        self.workbook(route, rows=0)

    def test_expenses_current_petty_cash_surface_filter_dates_and_text(self):
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="S",
            name="کارگاه شمال",
        )
        phase = ProjectPhase.objects.create(
            organization=self.organization, site=site, code="P", name="اجرای شمال"
        )
        from apps.expenses.models import PlatformExpenseGroup

        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "سایر هزینه‌ها"}
        )
        self.expense = create_expense(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            phase=phase,
            description='=HYPERLINK("https://example.invalid")',
            amount=Decimal("12345.67"),
            incurred_on=date(2026, 11, 3),
            receipt_reference="0007",
        )
        self.login(self.owner)
        route = reverse("expenses:list")
        wb = self.workbook(route, {"project": "اجرای شمال"}, rows=1)
        self.assertEqual(wb.active["B2"].value, site.name)
        self.assertEqual(wb.active["G2"].data_type, "s")
        self.assertEqual(wb.active["K2"].value, 12345.67)
        self.assertEqual(wb.active["M2"].value, "0007")
        self.workbook(route, {"description": "missing-export"}, rows=0)
        self.workbook(route, {"incurred_on_from": "2027-01-01"}, rows=0)
        self.login(self.outsider)
        self.workbook(route, rows=0)

    def test_all_operational_exports_deny_missing_permission_and_cancelled_tenant(self):
        from apps.accounts.models import User

        user = User.objects.create_user(username="no-export-rights")
        self.organization.memberships.create(user=user, role="viewer", status="active")
        self.login(user)
        routes = [
            "procurement:request_list",
            "procurement:rfq_list",
            "procurement:order_list",
            "procurement:receipt_list",
            "inventory:transaction_list",
            "expenses:list",
        ]
        for route in routes:
            self.assertEqual(
                self.client.get(reverse(route), {"format": "xlsx"}).status_code, 403
            )
        self.login(self.owner)
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])
        for route in routes:
            self.assertIn(
                self.client.get(reverse(route), {"format": "xlsx"}).status_code,
                (302, 403),
            )

    def test_export_full_filtered_dataset_not_page_and_no_n_plus_one(self):
        from apps.procurement.services import (
            add_purchase_request_item,
            create_purchase_request,
            get_organization_purchase_requests,
        )
        from apps.procurement.xlsx_exports import procurement_download

        for i in range(4):
            record = create_purchase_request(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                request_number=f"XL-{i}",
                title="کالای موردنیاز",
            )
            add_purchase_request_item(
                organization=self.organization,
                actor=self.owner,
                purchase_request=record,
                material=self.material,
                quantity=Decimal(2),
            )

        def run():
            records = get_organization_purchase_requests(
                user=self.owner, organization=self.organization
            )
            with CaptureQueriesContext(connection) as captured:
                response = procurement_download(
                    "request", records, organization=self.organization
                )
                load_workbook(BytesIO(b"".join(response.streaming_content)))
            return len(captured)

        count = run()
        self.assertLessEqual(count, 3)
        self.login(self.owner)
        self.workbook(
            reverse("procurement:request_list"), {"page_size": "2", "page": "2"}, rows=4
        )
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        other = Project.objects.create(
            organization=self.organization, code="DENY", name="بدون دسترسی"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="explicit test scope",
        )
        self.workbook(reverse("procurement:request_list"), rows=0)


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class SplitSourcingExportTests(WorkbookAssertions, ConnectedJourneyFixture, TestCase):
    evidence_root = Path(__file__).resolve().parents[1] / "output/mvp-05/split"

    def test_split_source_lineage_prices_and_read_only_downloads(self):
        self.begin(suppliers=2)
        self.open_quotes_and_compare()
        award = self.award(["4", "6"])
        for index, allocation in enumerate(award.allocations.all(), 1):
            order = self.order_from(
                award, allocation.quote_revision.envelope.supplier, f"PO-XL-{index}"
            )
            self.receive_into_stock(order, str(allocation.quantity), index)
        before = self.money_snapshot()
        self.login(self.owner)
        wb = self.workbook(reverse("procurement:order_list"), rows=2)
        self.assertEqual(
            {wb.active.cell(i, 5).value for i in (2, 3)}, {self.rfq.rfq_number}
        )
        self.assertEqual(
            {wb.active.cell(i, 4).value for i in (2, 3)}, {self.pr.request_number}
        )
        self.assertEqual({wb["اقلام"].cell(i, 5).value for i in (2, 3)}, {4, 6})
        self.workbook(reverse("procurement:receipt_list"), rows=2)
        self.workbook(reverse("inventory:transaction_list"), rows=2)
        self.assertEqual(before, self.money_snapshot())
