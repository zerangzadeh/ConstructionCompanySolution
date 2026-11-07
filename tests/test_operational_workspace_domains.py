"""Browser coverage for mixed workspaces and retained Safety/Quality lists."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from test_daily_report_references import DailyReferenceFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.equipment.models import Equipment
from apps.equipment.p8_models import EquipmentWorkOrder
from apps.inventory.models import (
    InventoryCount,
    InventoryReservation,
    InventoryTransfer,
)
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from apps.timekeeping.models import AttendanceCorrectionRequest, LeaveMissionRequest
from apps.timekeeping.services import (
    add_timesheet_entry,
    capture_attendance,
    create_overtime_request,
    create_timesheet,
    create_work_calendar,
)
from apps.workforce.test_mvp02 import make_field_fixture

GEOMETRY = "document.documentElement.scrollWidth<=innerWidth+1 && getComputedStyle(document.querySelector('main')).direction==='rtl' && document.querySelectorAll('main h1').length===1"
COMMON = {
    "status": 200,
    "screenshot": True,
    "viewportScreenshot": True,
    "fullPageScreenshot": True,
    "bottomScreenshot": True,
    "noJsErrors": True,
    "noHttpErrors": True,
}


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalDomainBrowserTests(DailyReferenceFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/operational-workspace/domains")

    def domain_fixture(self):
        self.setup_daily()
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="WS-U",
            name="عدد",
            symbol="عدد",
            category="count",
        )
        material = Material.objects.create(
            organization=self.organization,
            code="WS-M",
            name="قطعه نمونه انبار",
            unit_of_measure=unit,
        )
        self.reservation = InventoryReservation.objects.create(
            organization=self.organization,
            reservation_number="WS-RES-01",
            project=self.project,
            warehouse=self.warehouses[0],
            material=material,
            unit_of_measure=unit,
            quantity=Decimal(2),
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.count = InventoryCount.objects.create(
            organization=self.organization,
            count_number="WS-CNT-01",
            warehouse=self.warehouses[0],
            created_by=self.owner,
        )
        self.transfer = InventoryTransfer.objects.create(
            organization=self.organization,
            transfer_number="WS-TR-01",
            source_warehouse=self.warehouses[0],
            destination_warehouse=self.warehouses[1],
            created_by=self.owner,
        )
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="WS-EQ",
            name="بیل مکانیکی نمونه",
            category="ماشین‌آلات",
        )
        self.order = EquipmentWorkOrder.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            number="WS-WO-01",
            summary="بررسی سامانه هیدرولیک تجهیز",
            scheduled_for=timezone.localdate() - timedelta(days=1),
            created_by=self.owner,
        )
        self.field_project, self.field_site, _, self.employee, _ = make_field_fixture(
            self.owner, self.organization
        )
        calendar = create_work_calendar(
            organization=self.organization,
            actor=self.owner,
            code="WS-CAL",
            name="تقویم کارگاه",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
        )
        start = datetime.combine(
            date(2026, 11, 5), time(8), ZoneInfo(self.organization.settings.timezone)
        )
        self.attendance = capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            calendar=calendar,
            project=self.field_project,
            site=self.field_site,
            work_date=start.date(),
            check_in_at=start,
            check_out_at=start + timedelta(hours=8),
        )
        AttendanceCorrectionRequest.objects.create(
            organization=self.organization,
            attendance=self.attendance,
            kind="correction",
            reason="اصلاح ساعت خروج ثبت‌شده",
            replacement_check_in_at=start,
            replacement_check_out_at=start + timedelta(hours=9),
            requested_by=self.owner,
        )
        LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.employee,
            project=self.field_project,
            site=self.field_site,
            kind="leave",
            category_code="annual",
            starts_at=start + timedelta(days=1),
            ends_at=start + timedelta(days=1, hours=2),
            reason="درخواست مرخصی نمونه",
            requested_by=self.owner,
        )
        create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.field_project,
            site=self.field_site,
            starts_at=start + timedelta(hours=8),
            ends_at=start + timedelta(hours=10),
            reason="تکمیل کار روزانه",
        )
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=start.date(),
            period_end=start.date(),
            declared_minutes=480,
        )
        add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=start.date(),
            project=self.field_project,
            site=self.field_site,
            minutes=480,
        )

    def test_populated_domains_navigation_filters_and_restrictions(self):
        self.domain_fixture()
        routes = [
            ("inventory", "inventory:custody_workbench"),
            ("equipment", "equipment:operations_workbench"),
            ("timekeeping", "timekeeping:workbench"),
            ("safety", "safety:list"),
            ("quality", "quality:list"),
        ]
        for name, route in routes:
            self.browser(
                self.owner,
                [
                    dict(
                        COMMON,
                        name=f"{name}-{width}",
                        path=reverse(route),
                        width=width,
                        steps=[
                            {
                                "inspect": GEOMETRY,
                                "description": "one heading, RTL and responsive geometry",
                            }
                        ],
                    )
                    for width in (1440, 1024, 390)
                ],
            )
        self.browser(
            self.owner,
            [
                dict(
                    COMMON,
                    name="inventory-count-navigation",
                    path=reverse("inventory:custody_workbench"),
                    width=390,
                    steps=[
                        {
                            "clickSelector": "main a[href='"
                            + reverse("inventory:count_detail", args=[self.count.pk])
                            + "']",
                            "afterPath": reverse(
                                "inventory:count_detail", args=[self.count.pk]
                            ),
                        },
                        {
                            "history": "back",
                            "afterPath": reverse("inventory:custody_workbench"),
                        },
                    ],
                ),
                dict(
                    COMMON,
                    name="equipment-follow-up-navigation",
                    path=reverse("equipment:operations_workbench"),
                    width=390,
                    steps=[
                        {
                            "clickSelector": "main a[href='"
                            + reverse(
                                "equipment:work_order_transition", args=[self.order.pk]
                            )
                            + "']",
                            "afterPath": reverse(
                                "equipment:work_order_transition", args=[self.order.pk]
                            ),
                        },
                        {
                            "history": "back",
                            "afterPath": reverse("equipment:operations_workbench"),
                        },
                    ],
                ),
                dict(
                    COMMON,
                    name="timekeeping-date-filter",
                    path=reverse("timekeeping:workbench") + "?date_from=2026-11-06",
                    width=390,
                    mustText=["سابقه حضوری برای نمایش وجود ندارد."],
                    steps=[
                        {
                            "inspect": GEOMETRY,
                            "description": "filtered empty history geometry",
                        }
                    ],
                ),
            ],
        )
        for domain in ("safety", "quality"):
            self.browser(
                self.owner,
                [
                    dict(
                        COMMON,
                        name=f"{domain}-filter-clear",
                        path=reverse(domain + ":list"),
                        width=390,
                        steps=[
                            {
                                "fill": {"number": "MISSING-RECORD"},
                                "formSelector": "#list-filter-bar",
                                "submit": True,
                                "afterPath": reverse(domain + ":list"),
                            },
                            {
                                "inspect": "document.querySelectorAll('.erp-responsive-list tbody tr').length===0 && !!document.querySelector('.erp-list-chip')",
                                "description": "filtered list retains active chips",
                            },
                            {
                                "clickSelector": ".erp-list-clear",
                                "afterPath": reverse(domain + ":list"),
                            },
                            {
                                "inspect": "document.querySelectorAll('.erp-responsive-list tbody tr').length===1",
                                "description": "clear restores scoped source records",
                            },
                            {"history": "back", "afterPath": reverse(domain + ":list")},
                        ],
                    )
                ],
            )
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "equipment_operations.view",
                    "attendance.view",
                    "safety_incidents.view",
                    "quality_issues.view",
                    "inventory_reconciliations.view",
                    "inventory_reservations.view",
                    "inventory_counts.view",
                    "inventory_transfers.view",
                ]
            )
        )
        # Explicit test-only organization read scope; no mutation grant.
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.reader_scope.membership,
            scope_type="organization",
            reason="Synthetic workspace browser read scope",
        )
        for name, route in routes:
            self.browser(
                self.reader,
                [
                    dict(
                        COMMON,
                        name=f"{name}-reader",
                        path=reverse(route),
                        width=390,
                        steps=[
                            {
                                "inspect": "!document.querySelector('main form[method=post] button')",
                                "description": "read-only membership has no workspace mutation controls",
                            }
                        ],
                    )
                ],
            )
        for name, route in routes:
            self.browser(
                self.denied,
                [
                    {
                        "name": f"{name}-denied",
                        "path": reverse(route),
                        "width": 390,
                        "status": 403,
                        "screenshot": True,
                        "plainBusinessDenial": True,
                    }
                ],
            )

    def test_empty_mixed_workspaces(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )
        from apps.organizations.models import OrganizationSettings

        synchronize_authorization_catalog(using="default")
        self.make_fixture()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"timezone": "Asia/Tehran"}
        )
        self.login(self.owner)
        for name, route in [
            ("inventory", "inventory:custody_workbench"),
            ("equipment", "equipment:operations_workbench"),
            ("timekeeping", "timekeeping:workbench"),
            ("safety", "safety:list"),
            ("quality", "quality:list"),
        ]:
            self.browser(
                self.owner,
                [
                    dict(
                        COMMON,
                        name=f"{name}-empty-{width}",
                        path=reverse(route),
                        width=width,
                        steps=[
                            {
                                "inspect": GEOMETRY,
                                "description": "empty workspace RTL geometry",
                            }
                        ],
                    )
                    for width in (1440, 1024, 390)
                ],
            )
